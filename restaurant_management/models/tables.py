from odoo import models, fields, api
from odoo.tools import ormcache

class RestaurantTable(models.Model):
    _name='restaurant.table'
    _description='Restaurant Table'
    _rec_name='name'
    _order='name asc'

    name = fields.Char(string='Table Name', required=True)

    active = fields.Boolean(string='Archived switch', default=True)
    capacity = fields.Integer(
        string='Capacity',
        required=True,
        default=2
    )

    location = fields.Selection([
    ('indoor', 'Indoor'),
    ('terrace', 'Terrace'),
    ('private', 'Private'),
    ], string='Location / Section', default='indoor', required=True)

    reservation_ids = fields.One2many(
        'restaurant.reservation', 'table_id', string='Reservations')
    
    order_ids = fields.One2many(
        'restaurant.order',
        'table_id',
        string='Orders')
    
    reservation_count = fields.Integer(compute='_compute_reservation_count')
    active_order_count = fields.Integer(compute='_compute_active_order_count')

    availability = fields.Selection(
        [('available', 'Available'), ('reserved', 'Reserved now')],
        compute='_compute_availability', store=True, string='Status now')
    
    is_available = fields.Boolean(
        string='Available',
        compute='_compute_availability',
        store=True)

    def _compute_reservation_count(self):
        for rec in self:
            rec.reservation_count = len(rec.reservation_ids)

    @api.depends('order_ids.state')
    def _compute_active_order_count(self):
        active_states = ('confirmed', 'preparing', 'ready')
        for table in self:
            table.active_order_count = len(
                table.order_ids.filtered(lambda order: order.state in active_states)
            )

    def action_view_active_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Active Orders',
            'res_model': 'restaurant.order',
            'view_mode': 'tree,form',
            'domain': [
                ('table_id', '=', self.id),
                ('state', 'in', ['confirmed', 'preparing', 'ready']),
            ],
            'context': {'default_table_id': self.id},
        }

    @api.depends(
    'reservation_ids.state',
    'reservation_ids.reservation_date',
    'reservation_ids.reservation_end',
    'order_ids.state',
    'order_ids.reservation_time',
    'order_ids.end_time')
    def _compute_availability(self):
        now = fields.Datetime.now()

        # Tables currently occupied by reservations
        reserved_tables = self.env['restaurant.reservation'].search([
            ('table_id', 'in', self.ids),
            ('state', 'in', ('confirmed', 'seated')),
            ('reservation_date', '<=', now),
            ('reservation_end', '>', now),
        ]).mapped('table_id')

        # Tables currently occupied by orders
        occupied_tables = self.env['restaurant.order'].search([
            ('table_id', 'in', self.ids),
            ('state', 'in', ('confirmed', 'preparing', 'ready')),
        ]).mapped('table_id')

        for table in self:
            if table in reserved_tables or table in occupied_tables:
                table.availability = 'reserved'
                table.is_available = False
            else:
                table.availability = 'available'
                table.is_available = True

    @api.model
    def _cron_refresh_availability(self):
        """Runs every minute: re-evaluates every table against the current time."""
        tables = self.with_context(active_test=False).search([])
        self.env.add_to_compute(self._fields['availability'], tables)
        self.env.add_to_compute(self._fields['is_available'], tables)
        self.env.flush_all()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('restaurant.table') or 'New'
        return super().create(vals_list)

    @ormcache('self.id', 'start', 'end', 'exclude_order')
    def is_available_for_period(self, start, end, exclude_order=None):
        """Return True if the table is free during the given period."""

        if not start or not end:
            return False

        if start >= end:
            return False

        # Check overlapping reservations
        reservation = self.env['restaurant.reservation'].search([
            ('table_id', '=', self.id),
            ('state', 'in', ('confirmed', 'seated')),
            ('reservation_date', '<', end),
            ('reservation_end', '>', start),
        ], limit=1)

        if reservation:
            return False

        # Check overlapping orders
        order_domain = [
            ('table_id', '=', self.id),
            ('state', 'in', (
                'confirmed',
                'preparing',
                'ready',
            )),
            ('reservation_time', '<', end),
            ('end_time', '>', start),
        ]

        if exclude_order:
            order_domain.append(('id', '!=', exclude_order.id))

        order = self.env['restaurant.order'].search(
            order_domain,
            limit=1
        )

        if order:
            return False

        return True