from odoo import exceptions, models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta

class RestaurantOrder(models.Model):

    _name = 'restaurant.order'
    _description = 'Restaurant Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reservation_time desc'

    name = fields.Char(
        string='Order Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New'
    )

    customer_id = fields.Many2one(
        'restaurant.customer',
        string='Customer',
        required=True,
        ondelete='restrict'
    )
    date_order = fields.Datetime(string='Order Date', required=True, default=fields.Datetime.now)

    table_id = fields.Many2one('restaurant.table', string='Table')
    
    order_type = fields.Selection([
        ('dine_in', 'Dine In'),
        ('takeaway', 'Takeaway'),
        ('delivery', 'Delivery'),
    ], string='Order Type', required=True)

    table_id = fields.Many2one(
        'restaurant.table',
        string='Table'
    )

    reservation_time = fields.Datetime(
        string='Reservation Time'
    )

    duration_minutes = fields.Integer(
        string='Duration (Minutes)',
        default=90
    )

    end_time = fields.Datetime(
        string='End Time',
        compute='_compute_end_time',
        store=True
    )

    line_ids = fields.One2many(
        'restaurant.order.line',
        'order_id',
        string='Order Lines',
        required=True
    )

    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_amounts',
        store=True
    )

    tax_amount = fields.Float(
        string='Tax',
        compute='_compute_amounts',
        store=True
    )

    delivery_fee = fields.Float(
        string='Delivery Fee',
        default=0.0
    )

    total_amount = fields.Float(
        string='Total Amount',
        compute='_compute_amounts',
        store=True
    )

    delivery_address = fields.Text(
        string='Delivery Address'
    )

    driver_id = fields.Many2one(
        'res.users',
        string='Driver'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ], string='Status', required=True, default='draft')

    payment_status = fields.Selection([
        ('current', 'Current'),
        ('upcoming', 'Upcoming'),
        ('overdue', 'Overdue'),
    ], string='Payment Status')

    next_payment_date = fields.Date(
        string='Next Payment Date'
    )

    days_overdue = fields.Integer(
        string='Days Overdue'
    )

    last_reminder_sent = fields.Datetime(
        string='Last Reminder Sent'
    )

    external_id = fields.Char(
        string='External ID',
        copy=False,
        index=True
    )

    notes = fields.Text(
        string='Notes'
    )

    order_items = fields.Text(
        string='Order Items',
        compute='_compute_order_items'
    )

    payment_ids = fields.One2many(
        'restaurant.payment',
        'order_id',
        string='Payments'
    )

    @api.depends('reservation_time', 'duration_minutes')
    def _compute_end_time(self):
        for order in self:
            if order.reservation_time and order.duration_minutes:
                order.end_time = fields.Datetime.add(
                    order.reservation_time,
                    minutes=order.duration_minutes
                )
            else:
                order.end_time = False

    @api.constrains('reservation_time', 'duration_minutes')
    def _check_times(self):
        for order in self:
            if order.duration_minutes <= 0:
                raise ValidationError(
                    'Duration must be greater than 0 minutes.'
                )

    @api.depends(
        'line_ids.price_subtotal',
        'line_ids.tax_amount',
        'line_ids.total_amount',
        'delivery_fee',
    )
    def _compute_amounts(self):
        for order in self:
            order.subtotal = sum(order.line_ids.mapped('price_subtotal'))
            order.tax_amount = sum(order.line_ids.mapped('tax_amount'))
            order.total_amount = (
                sum(order.line_ids.mapped('total_amount'))
                + order.delivery_fee
            )

    @api.depends('line_ids.menu_item_id', 'line_ids.quantity')
    def _compute_order_items(self):
        for order in self:
            items = []

            for line in order.line_ids:
                if line.menu_item_id:
                    items.append(
                        f"{line.quantity} x {line.menu_item_id.name}"
                    )

            order.order_items = '\n'.join(items)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('restaurant.order')
                    or 'New'
                )

        return super().create(vals_list)

    @api.constrains('order_type', 'table_id', 'delivery_address')
    def _check_type_rules(self):
        for order in self:

            if order.order_type == 'dine_in' and not order.table_id:
                raise ValidationError(
                    'A table is required for dine-in orders.'
                )

            if order.order_type == 'delivery' and not order.delivery_address:
                raise ValidationError(
                    'A delivery address is required for delivery orders.'
                )
        
    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_prepare(self):
        self.write({'state': 'preparing'})

    def action_ready(self):
        self.write({'state': 'ready'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_no_show(self):
        self.write({'state': 'no_show'})



    @api.model
    def _cron_close_stale_orders(self):
        cutoff = fields.Datetime.now() - timedelta(minutes=30)

        stale_orders = self.search([
            ('state', '=', 'confirmed'),
            ('end_time', '<', cutoff),
        ])
        for order in stale_orders:

            order.state = 'no_show'

            if order.table_id:
                order.table_id.available = True


    @api.constrains('line_ids')
    def _check_order_lines(self):
        for order in self:
            if not order.line_ids:
                raise ValidationError(
                    'You must add at least one item to the order.'
                )

    def write(self, vals):
        for order in self:

            # Preparing:
            # Only allow changing state from preparing -> ready
            if order.state == 'preparing':
                if vals.keys() != {'state'} or vals.get('state') != 'ready':
                    raise ValidationError(
                        'While the order is being prepared, '
                        'you can only mark it as Ready.'
                    )

            # After preparing:
            # Completely lock the order
            elif order.state in (
                'ready',
                'completed',
                'cancelled',
                'no_show',
            ):
                raise ValidationError(
                    'This order cannot be edited because it is already '
                    'Ready, Completed, Cancelled, or No Show.'
                )

        return super().write(vals)