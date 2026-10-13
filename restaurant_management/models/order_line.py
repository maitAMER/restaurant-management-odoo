from odoo import models, fields, api
from odoo.exceptions import ValidationError

class RestaurantOrderLine(models.Model):

    _name = 'restaurant.order.line'
    _description = 'Restaurant Order Line'

    TAX_RATE = 0.14

    order_id = fields.Many2one(
        'restaurant.order',
        string='Order',
        required=True,
        ondelete='cascade'
    )

    menu_item_id = fields.Many2one(
        'restaurant.menu.item',
        string='Menu Item',
        required=True
    )

    description = fields.Text(
        string='Description'
    )

    quantity = fields.Float(
        string='Quantity',
        required=True,
        default=1.0
    )

    unit_price = fields.Float(
        string='Unit Price',
        required=True
    )

    price_subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_price_subtotal',
        store=True
    )

    tax_amount = fields.Float(
        string='Tax Amount',
        compute='_compute_amounts',
        store=True
    )

    total_amount = fields.Float(
        string='Total Amount',
        compute='_compute_amounts',
        store=True
    )

    notes = fields.Text(
        string='Notes'
    )

    @api.depends('quantity', 'unit_price')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = (
                line.quantity * line.unit_price
            )

    @api.depends('price_subtotal')
    def _compute_amounts(self):
        for line in self:
            line.tax_amount = line.price_subtotal * self.TAX_RATE
            line.total_amount = line.price_subtotal + line.tax_amount

    @api.onchange('menu_item_id')
    def _onchange_menu_item_id(self):
        if self.menu_item_id:
            self.unit_price = self.menu_item_id.price
            self.description = self.menu_item_id.name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            order = self.env['restaurant.order'].browse(
                vals.get('order_id')
            )

            if order.state in (
                'preparing',
                'ready',
                'completed',
                'cancelled',
                'no_show',
            ):
                raise ValidationError(
                    'You cannot add items to an order that is '
                    'being prepared or already finalized.'
                )

        return super().create(vals_list)


    def write(self, vals):
        for line in self:
            if line.order_id.state in (
                'preparing',
                'ready',
                'completed',
                'cancelled',
                'no_show',
            ):
                raise ValidationError(
                    'You cannot edit items when the order is '
                    'being prepared or already finalized.'
                )

        return super().write(vals)


    def unlink(self):
        for line in self:
            if line.order_id.state in (
                'preparing',
                'ready',
                'completed',
                'cancelled',
                'no_show',
            ):
                raise ValidationError(
                    'You cannot remove items when the order is '
                    'being prepared or already finalized.'
                )

        return super().unlink()