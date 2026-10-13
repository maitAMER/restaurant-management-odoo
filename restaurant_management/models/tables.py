from odoo import models, fields, api


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
    reservation_count = fields.Integer(compute='_compute_reservation_count')

    availability = fields.Selection(
        [('available', 'Available'), ('reserved', 'Reserved now')],
        compute='_compute_availability', store=True, string='Status now')
    is_available = fields.Boolean(
        string='Active', compute='_compute_availability', store=True)

    def _compute_reservation_count(self):
        for rec in self:
            rec.reservation_count = len(rec.reservation_ids)

    @api.depends('reservation_ids.state',
                 'reservation_ids.reservation_date',
                 'reservation_ids.reservation_end')
    def _compute_availability(self):
        now = fields.Datetime.now()
        busy = self.env['restaurant.reservation'].search([
            ('table_id', 'in', self.ids),
            ('state', 'in', ('confirmed', 'seated')),
            ('reservation_date', '<=', now),
            ('reservation_end', '>', now),
        ]).mapped('table_id')
        for rec in self:
            reserved = rec in busy
            rec.availability = 'reserved' if reserved else 'available'
            rec.is_available = not reserved

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
