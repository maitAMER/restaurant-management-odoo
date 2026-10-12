from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


class RestaurantReservation(models.Model):
    _name = 'restaurant.reservation'
    _description = 'Restaurant Reservation'
    _order = 'reservation_date desc'

    name = fields.Char(string='Reservation', copy=False, default='New', readonly=True)
    customer_id = fields.Many2one('restaurant.customer', string='Customer')
    table_id = fields.Many2one('restaurant.table', string='Table')
    reservation_date = fields.Datetime(string='Start', required=True)
    duration = fields.Float(string='Duration (hours)', default=1.5)
    reservation_end = fields.Datetime(string='End', compute='_compute_end', store=True)
    guests = fields.Integer(string='Guests', required=True, default=2)
    reminder_sent = fields.Boolean(string='Reminder Sent', default=False, copy=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('seated', 'Seated'),
        ('no_show', 'No-show'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='confirmed', required=True)

    @api.depends('reservation_date', 'duration')
    def _compute_end(self):
        for rec in self:
            if rec.reservation_date:
                rec.reservation_end = rec.reservation_date + timedelta(hours=rec.duration or 1)
            else:
                rec.reservation_end = False

    @api.depends('table_id', 'customer_id', 'guests')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f"{rec.table_id.display_name or ''} "
                f"{rec.customer_id.display_name or ''} "
                f"({rec.guests})"
            )

    @api.constrains('table_id', 'reservation_date', 'duration', 'state', 'guests')
    def _check_table_availability(self):
        for rec in self:
            if not rec.table_id or not rec.reservation_date:
                continue

            if rec.duration <= 0:
                raise ValidationError("Reservation duration must be greater than zero.")

            if rec.state in ('cancelled', 'no_show'):
                continue

            if rec.guests > rec.table_id.capacity:
                raise ValidationError(
                    f"Table {rec.table_id.name} seats {rec.table_id.capacity} "
                    f"guests, but this reservation is for {rec.guests}."
                )

            overlapping = self.search([
                ('id', '!=', rec.id),
                ('table_id', '=', rec.table_id.id),
                ('state', 'not in', ('cancelled', 'no_show')),
                ('reservation_date', '<', rec.reservation_end),
                ('reservation_end', '>', rec.reservation_date),
            ])
            if overlapping:
                raise ValidationError(
                    f"Table {rec.table_id.name} is already reserved by "
                    f"{overlapping[0].customer_id.name or overlapping[0].name} "
                    f"during this time. Please choose another time or table."
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('restaurant.reservation') or 'New'
                )
        return super().create(vals_list)

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_seat(self):
        self.write({'state': 'seated'})

    def action_no_show(self):
        self.write({'state': 'no_show'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    @api.model
    def _cron_send_reservation_reminders(self):
        now = fields.Datetime.now()

        reservations = self.search([
            ('state', '=', 'confirmed'),
            ('reminder_sent', '=', False),
            ('reservation_date', '>=', now + timedelta(hours=23)),
            ('reservation_date', '<', now + timedelta(hours=25)),
        ])

        template = self.env.ref(
            'restaurant_management.email_template_reservation_reminder',
            raise_if_not_found=False
        )
        if not template:
            return

        for reservation in reservations:
            if not reservation.customer_id.email:
                continue
            template.send_mail(reservation.id, force_send=True)
            reservation.reminder_sent = True

    @api.model
    def _cron_flag_no_show_reservations(self):
        cutoff = fields.Datetime.now() - timedelta(minutes=15)

        reservations = self.search([
            ('state', '=', 'confirmed'),
            ('reservation_date', '<', cutoff),
        ])
        reservations.write({'state': 'no_show'})