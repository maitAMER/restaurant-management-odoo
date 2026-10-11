from odoo import models, fields, api

class RestaurantOrderLine(models.Model):
    _name = 'restaurant.order.line'
    _description = 'Restaurant Order Line'

    order_id = fields.Many2one('restaurant.order', string='Order', required=True, ondelete='cascade')

    product_id = fields.Many2one(
        'restaurant.menu.item', string='Menu Item', required=True,
    )
    menu_section = fields.Selection(
        related='product_id.menu_section', string='Menu Section', readonly=True,
    )

    quantity = fields.Float(string='Quantity', required=True, default=1.0)

    price_unit = fields.Float(string='Unit Price', required=True)

    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal', store=True)

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.price
