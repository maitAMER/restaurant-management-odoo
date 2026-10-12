from odoo import models, fields, api

class RestaurantOrder(models.Model):
    _name = 'restaurant.order'
    _description = 'Restaurant Order'
    _order = 'date_order desc'

    name = fields.Char(string='Order Reference', required=True, copy=False, readonly=True, default=lambda self: ('New'))
    
    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    
    date_order = fields.Datetime(string='Order Date', required=True, default=fields.Datetime.now)
    
    order_type = fields.Selection([
        ('dine_in', 'Dine In'), 
        ('takeaway', 'Takeaway'), 
        ('delivery', 'Delivery')], string='Order Type', required=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    ], string='Status', required=True, default='draft')

    order_line_ids = fields.One2many('restaurant.order.line', 'order_id', string='Order Lines')
        
      #حطيت ده يا انجي علشان اعرف اربط  و مخليش الاوردر الي ادفع عليه يدفع عليه حاجه تاني
    payment_ids = fields.One2many('restaurant.payment','order_id',string='Payments')

    notes= fields.Text(string='Notes')

    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)

    order_items = fields.Text(
    string='Order Items',
    compute='_compute_order_items')

    @api.depends('order_line_ids.product_id', 'order_line_ids.quantity')
    def _compute_order_items(self):
        for order in self:
            items = []

            for line in order.order_line_ids:
                items.append(
                    f"{line.quantity} x {line.product_id.name}" )

            order.order_items = '\n'.join(items)

    @api.depends('order_line_ids.subtotal')
    def _compute_total_amount(self):
        for order in self:
            order.total_amount = sum(order.order_line_ids.mapped('subtotal'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('restaurant.order') or 'New'
        return super().create(vals_list)

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_prepare(self):
        self.write({'state': 'preparing'})

    def action_ready(self):
        self.write({'state': 'ready'})

    def action_deliver(self):
        self.write({'state': 'delivered'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})