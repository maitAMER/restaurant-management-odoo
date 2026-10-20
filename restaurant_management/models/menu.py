from odoo import api, fields, models
from odoo.exceptions import ValidationError

class RestaurantMenuCategory(models.Model):
    _name = 'restaurant.menu.category'
    _description = 'Restaurant Menu Category'
    _order = 'sequence, name'

    name = fields.Char(string='Category Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    item_ids = fields.One2many(
        'restaurant.menu.item', 'category_id', string='Menu Items',
    )

class RestaurantMenuItem(models.Model):
    _name = 'restaurant.menu.item'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Restaurant Menu Item'
    _order = 'daily_special desc, menu_section, name, id'

    name = fields.Char(string='Menu Item', required=True, tracking=True)
    image_1920 = fields.Image(string='Pizza Image', max_width=1920, max_height=1920)
    # Retained for compatibility with records created before menu sections were added.
    category_id = fields.Many2one(
        'restaurant.menu.category', string='Pizza Category',
        ondelete='restrict', tracking=True,
    )
    order_line_ids = fields.One2many(
        'restaurant.order.line', 'menu_item_id', string='Order Lines',
    )
    total_sold_qty = fields.Float(
        string='Total Sold', compute='_compute_total_sold_qty',
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


    ingredients = fields.Text(string='Ingredients')
    pizza_type = fields.Selection(
            [
                ('pepperoni', 'Pepperoni'),
                ('margherita', 'Margherita'),
                ('hawaiian', 'Hawaiian'),
                ('meat_lovers', 'Meat Lovers'),
                ('supreme', 'Supreme'),
                ('bbq_chicken', 'BBQ Chicken'),
                ('quattro_formaggi', 'Four Cheese'),
                ('vegetarian', 'Vegetarian'),
                ('neapolitan', 'Neapolitan'),
                ('sicilian', 'Sicilian'),
                ('roman', 'Roman'),
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
    cost = fields.Float(
        string='Cost', required=True, digits='Product Price',
        groups="restaurant_management.group_shift_manager",
    )
    gross_profit = fields.Float(
        string='Profit', compute='_compute_profit',
        groups="restaurant_management.group_shift_manager",
        digits='Product Price', store=True, compute_sudo=True,
    )
    margin = fields.Float(
        string='Margin', compute='_compute_profit',
        groups="restaurant_management.group_shift_manager",
        digits=(16, 2), store=True, compute_sudo=True,
    )

    prep_time = fields.Integer(
        string='Preparation Time',
        help='Preparation duration in minutes.',
    )
    prep_time_minutes = fields.Integer(
        string='Preparation Time (Minutes)', related='prep_time', readonly=False,
        store=True,
    )
    prep_time_display = fields.Char(
        string='Preparation Time',
        compute='_compute_prep_time_display',
    )
    availability = fields.Boolean(string='Available', default=True, help="Toggle if the item is currently available or out of stock from the kitchen", tracking=True)
    is_available = fields.Boolean(
        string='Available', related='availability', readonly=False, store=True,
    )
    daily_special = fields.Boolean(string='Daily Special', default=False, tracking=True)
    description = fields.Text(string='Description')
    allergens = fields.Text(string='Allergen Warnings', help="e.g., Contains dairy/cheese, gluten")

    @api.depends('order_line_ids.quantity', 'order_line_ids.order_id.state')
    def _compute_total_sold_qty(self):
        for item in self:
            item.total_sold_qty = sum(
                line.quantity
                for line in item.order_line_ids
                if line.order_id.state == 'completed'
            )

    def action_view_sales(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Completed Sales',
            'res_model': 'restaurant.order.line',
            'view_mode': 'tree',
            'views': [(self.env.ref(
                'restaurant_management.view_restaurant_order_line_sales_tree'
            ).id, 'tree')],
            'domain': [
                ('menu_item_id', '=', self.id),
                ('order_id.state', '=', 'completed'),
            ],
            'context': {'default_menu_item_id': self.id},
        }

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
            item.margin = (item.gross_profit / item.price) if item.price else 0.0

    @api.constrains('price', 'cost', 'prep_time')
    def _check_nonnegative_values(self):
        for item in self:
            if item.price <= 0:
                raise ValidationError('Enter a price greater than zero.')
            if item.cost <= 0:
                raise ValidationError('Enter a cost greater than zero.')
            if item.prep_time < 0:
                raise ValidationError('Preparation time cannot be negative.')

    @api.onchange('menu_section')
    def _onchange_menu_section(self):
        if self.menu_section != 'pizza':
            self.pizza_type = False
