from odoo import api, fields, models
from odoo.exceptions import ValidationError

class RestaurantMenuCategory(models.Model):
    _name = 'restaurant.menu.category'
    _description = 'Restaurant Menu Category'
    _order = 'sequence, name'

    name = fields.Char(string='Category Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)

class RestaurantMenuItem(models.Model):
    _name = 'restaurant.menu.item'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Restaurant Menu Item'
    _order = 'menu_section, name, id'

    MINIMUM_INGREDIENTS = 4

    name = fields.Char(string='Menu Item', required=True, tracking=True)
    image_1920 = fields.Image(string='Pizza Image', max_width=1920, max_height=1920)
    # Retained for compatibility with records created before menu sections were added.
    category_id = fields.Many2one(
        'restaurant.menu.category', string='Legacy Pizza Category',
        ondelete='restrict', tracking=True,
    )
    menu_section = fields.Selection(
        [
            ('pizza', 'Pizza'),
            ('dessert_appetizer', 'Desserts & Appetizers'),
            ('drink', 'Drinks'),
        ],
        string='Menu Section',
        required=True,
        default='pizza',
        tracking=True,
    )
    pizza_type = fields.Selection(
        [
            ('roman', 'Roman'),
            ('pepperoni', 'Pepperoni'),
            ('margherita', 'Margherita'),
            ('other', 'Other'),
        ],
        string='Pizza Type',
        tracking=True,
    )
    size = fields.Selection(
        [
            ('small', 'Small'),
            ('medium', 'Medium'),
            ('large', 'Large'),
            ('extra_large', 'Extra Large'),
        ],
        string='Size',
        required=True,
        default='medium',
        tracking=True,
    )
    
    price = fields.Float(string='Price', required=True, digits='Product Price', tracking=True)
    cost = fields.Float(string='Cost', digits='Product Price', tracking=True)
    gross_profit = fields.Float(string='Profit', compute='_compute_profit', digits='Product Price')
    margin_percent = fields.Float(string='Margin %', compute='_compute_profit', digits=(16, 2))
    prep_time = fields.Integer(
        string='Preparation Time',
        help='Preparation duration in minutes.',
    )
    prep_time_display = fields.Char(
        string='Preparation Time',
        compute='_compute_prep_time_display',
    )
    availability = fields.Boolean(string='Available', default=True, help="Toggle if the item is currently available or out of stock from the kitchen", tracking=True)
    ingredient_line_ids = fields.One2many(
        'restaurant.menu.ingredient', 'item_id', string='Ingredients',
    )
    ingredient_count = fields.Integer(
        string='Ingredient Count', compute='_compute_ingredient_status',
    )
    ingredient_warning = fields.Char(
        string='Ingredient Warning', compute='_compute_ingredient_status',
    )
    ingredients = fields.Text(string='Main Ingredients', help="e.g., Tomato sauce, mozzarella, flour")
    ingredient_search_text = fields.Char(
        string='Ingredient Search', compute='_compute_ingredient_search_text', store=True,
    )
    allergens = fields.Text(string='Allergen Warnings', help="e.g., Contains dairy/cheese, gluten")

    def init(self):
        # Merge values from the former separate Dessert and Appetizer sections.
        self.env.cr.execute("""
            UPDATE restaurant_menu_item
               SET menu_section = 'dessert_appetizer'
             WHERE menu_section IN ('dessert', 'appetizer')
        """)

    @api.depends('prep_time')
    def _compute_prep_time_display(self):
        for item in self:
            item.prep_time_display = f'{item.prep_time} min' if item.prep_time else '0 min'

    @api.depends('price', 'cost')
    def _compute_profit(self):
        for item in self:
            item.gross_profit = item.price - item.cost
            item.margin_percent = (item.gross_profit / item.price) if item.price else 0.0

    @api.depends('ingredients', 'ingredient_line_ids.name')
    def _compute_ingredient_search_text(self):
        for item in self:
            line_names = item.ingredient_line_ids.mapped('name')
            item.ingredient_search_text = ', '.join(filter(None, [item.ingredients, *line_names]))

    @api.constrains('price', 'cost', 'prep_time')
    def _check_nonnegative_values(self):
        for item in self:
            if item.price < 0 or item.cost < 0 or item.prep_time < 0:
                raise ValidationError('Price, cost, and preparation time cannot be negative.')

    @api.depends('ingredient_line_ids')
    def _compute_ingredient_status(self):
        for item in self:
            item.ingredient_count = len(item.ingredient_line_ids)
            item.ingredient_warning = (
                f'Add at least {self.MINIMUM_INGREDIENTS} ingredients. '
                f'This pizza currently has {item.ingredient_count}.'
                if item.ingredient_count < self.MINIMUM_INGREDIENTS
                else False
            )

    @api.onchange('menu_section')
    def _onchange_menu_section(self):
        if self.menu_section != 'pizza':
            self.pizza_type = False


class RestaurantMenuIngredient(models.Model):
    _name = 'restaurant.menu.ingredient'
    _description = 'Pizza Ingredient'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    item_id = fields.Many2one(
        'restaurant.menu.item', string='Pizza', required=True, ondelete='cascade',
    )
    name = fields.Char(string='Ingredient', required=True)
    quantity = fields.Float(
        string='Quantity', required=True, digits='Product Unit of Measure',
    )
    unit = fields.Selection(
        [
            ('g', 'g'), ('kg', 'kg'), ('ml', 'ml'), ('l', 'L'),
            ('tsp', 'tsp'), ('tbsp', 'tbsp'), ('piece', 'piece'),
        ],
        string='Unit', required=True,
    )

    @api.constrains('quantity')
    def _check_positive_quantity(self):
        if any(line.quantity <= 0 for line in self):
            raise ValidationError('Ingredient quantity must be greater than zero.')

    @api.constrains('name', 'item_id')
    def _check_duplicate_ingredient(self):
        for line in self.filtered(lambda record: record.name and record.item_id):
            normalized_name = line.name.strip().casefold()
            duplicates = line.item_id.ingredient_line_ids.filtered(
                lambda other: other != line
                and other.name
                and other.name.strip().casefold() == normalized_name
            )
            if duplicates:
                raise ValidationError(
                    f'{line.name} is already listed as an ingredient for this pizza.'
                )
