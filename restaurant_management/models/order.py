from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta

class RestaurantOrder(models.Model):

    _name = 'restaurant.order'
    _description = 'Restaurant Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reservation_time desc'

    name = fields.Char(string='Order Reference', required=True, copy=False, readonly=True, default='New')

    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    # Keep the existing res.partner relation intact for compatibility; this
    # link connects orders to the restaurant-specific customer records.
    restaurant_customer_id = fields.Many2one(
        'restaurant.customer', string='Restaurant Customer', ondelete='set null',
        help='Link the restaurant customer to award loyalty points when this order is delivered.',
    )
    loyalty_point_awarded = fields.Boolean(
        string='Loyalty Point Awarded', readonly=True, copy=False, default=False,
    )

    date_order = fields.Datetime(string='Order Date', required=True, default=fields.Datetime.now)

    order_type = fields.Selection([
        ('dine_in', 'Dine In'),
        ('takeaway', 'Takeaway'),
        ('delivery', 'Delivery'),
    ], string='Order Type', required=True)

    table_id = fields.Many2one(
        'restaurant.table',
        string='Table'
    )

    available_table_ids = fields.Many2many(
        'restaurant.table',
        compute='_compute_available_table_ids',
        string='Available Tables'
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

    @api.depends(
        'order_type',
        'reservation_time',
        'duration_minutes',
    )
    def _compute_available_table_ids(self):
        Table = self.env['restaurant.table']
        for order in self:
            if order.order_type != 'dine_in':
                order.available_table_ids = Table.browse()
                continue

            if not order.reservation_time or order.duration_minutes <= 0:
                order.available_table_ids = Table.search([
                    ('active', '=', True),
                ])
                continue

            end_time = fields.Datetime.add(
                order.reservation_time,
                minutes=order.duration_minutes,
            )

            available_tables = Table.search([
                ('active', '=', True),
            ]).filtered(
                lambda table: table.is_available_for_period(
                    order.reservation_time,
                    end_time,
                    exclude_order=order,
                )
            )

            order.available_table_ids = available_tables

    @api.onchange('order_type')
    def _onchange_order_type(self):
        if self.order_type == 'dine_in':
            self.delivery_address = False
            self.driver_id = False
            self.delivery_fee = 0.0
        elif self.order_type == 'delivery':
            self.table_id = False
            self.reservation_time = False
            self.duration_minutes = 90
        elif self.order_type == 'takeaway':
            self.table_id = False
            self.reservation_time = False
            self.duration_minutes = 90
            self.delivery_address = False
            self.driver_id = False
            self.delivery_fee = 0.0

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

    def _award_loyalty_points(self):
        transaction_model = self.env['restaurant.customer.loyalty.transaction']
        eligible_orders = self.filtered(
            lambda order: order.state == 'completed'
            and order.restaurant_customer_id
            and not order.loyalty_point_awarded
        )
        for order in eligible_orders:
            customer = order.restaurant_customer_id
            new_balance = customer.loyalty_points + 1
            customer.write({'loyalty_points': new_balance})
            transaction_model.create({
                'customer_id': customer.id,
                'date': fields.Datetime.now(),
                'points_delta': 1,
                'balance_after': new_balance,
                'reason': f'Loyalty point for order {order.name}',
                'source_order_id': order.id,
            })
            order.write({'loyalty_point_awarded': True})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('restaurant.order')
                    or 'New'
                )
        orders = super().create(vals_list)
        orders._clear_table_availability_cache()
        return orders

    def copy(self, default=None):
        default = dict(default or {})
        default.update({
            'state': 'draft',
            'reservation_time': False,
        })
        return super().copy(default)

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

    @api.model
    def _cron_close_stale_orders(self):
        cutoff = fields.Datetime.now() - timedelta(minutes=30)
        stale_orders = self.search([
            ('state', '=', 'confirmed'),
            ('end_time', '<', cutoff),
        ])
        for order in stale_orders:
            order.state = 'no_show'
        stale_orders._refresh_table_availability()

    @api.constrains('line_ids')
    def _check_order_lines(self):
        for order in self:
            if not order.line_ids:
                raise ValidationError(
                    'You must add at least one item to the order.'
                )

    def write(self, vals):
        for order in self:
            # Preparing: Only allow changing state to ready
            if order.state == 'preparing':
                if vals.keys() != {'state'} or vals.get('state') != 'ready':
                    raise ValidationError(
                        'While the order is being prepared, '
                        'you can only mark it as Ready.'
                    )
            # Ready: Can be completed or cancelled
            elif order.state == 'ready':
                if vals.keys() != {'state'} or vals.get('state') not in ('completed', 'cancelled'):
                    raise ValidationError(
                        'A ready order can only be completed or cancelled.'
                    )
            # Completed / Cancelled / No Show: locked except for loyalty points flag
            elif order.state in ('completed', 'cancelled', 'no_show'):
                if vals != {'loyalty_point_awarded': True}:
                    raise ValidationError(
                        'This order cannot be edited because it is already '
                        'Completed, Cancelled, or No Show.'
                    )

        result = super().write(vals)
        self._clear_table_availability_cache()

        if {'state', 'restaurant_customer_id'} & vals.keys():
            self._award_loyalty_points()

        return result

    def unlink(self):
        self._clear_table_availability_cache()
        return super().unlink()

    def _refresh_table_availability(self):
        tables = self.mapped('table_id')
        if tables:
            self.env.add_to_compute(
                tables._fields['availability'],
                tables
            )
            self.env.add_to_compute(
                tables._fields['is_available'],
                tables
            )
            self.env.flush_all()

    def _clear_table_availability_cache(self):
        tables = self.mapped('table_id')
        if tables:
            tables.is_available_for_period.clear_cache()

    def action_confirm(self):
        self.write({'state': 'confirmed'})
        self._refresh_table_availability()

    def action_prepare(self):
        self.write({'state': 'preparing'})
        self._refresh_table_availability()

    def action_ready(self):
        self.write({'state': 'ready'})
        self._refresh_table_availability()

    def action_complete(self):
        self.write({'state': 'completed'})
        self._refresh_table_availability()

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        self._refresh_table_availability()

    def action_no_show(self):
        self.write({'state': 'no_show'})
        self._refresh_table_availability()

    @api.constrains('table_id', 'reservation_time', 'duration_minutes')
    def _check_table_availability(self):
        for order in self:
            if not order.table_id:
                continue
            if not order.reservation_time:
                continue
            if not order.end_time:
                continue

            available = order.table_id.is_available_for_period(
                order.reservation_time,
                order.end_time,
                exclude_order=order,
            )

            if not available:
                raise ValidationError(
                    'This table is already reserved during the selected time. '
                    'Please choose another table or time.'
                )