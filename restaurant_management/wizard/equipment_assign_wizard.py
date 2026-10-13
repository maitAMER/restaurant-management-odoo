# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError


class RestaurantEquipmentAssignWizard(models.TransientModel):
    _name = 'restaurant.equipment.assign.wizard'
    _description = 'Assign Equipment Maintenance Tickets'

    ticket_ids = fields.Many2many(
        'restaurant.equipment.maintenance',
        string='Tickets',
        relation='restaurant_eq_assign_ticket_rel',
        column1='wizard_id',
        column2='ticket_id',
        default=lambda self: self.env['restaurant.equipment.maintenance'].browse(
            self.env.context.get('active_ids', [])
        ),
        readonly=True,
    )
    technician_id = fields.Many2one(
        'res.users', string='Technician', required=True,
    )

    def action_assign(self):
        self.ensure_one()
        if not self.ticket_ids:
            raise UserError('Select at least one maintenance ticket.')
        if any(ticket.state == 'done' for ticket in self.ticket_ids):
            raise UserError('Completed tickets cannot be assigned.')
        submitted_tickets = self.ticket_ids.filtered(
            lambda ticket: ticket.state == 'submitted'
        )
        submitted_tickets.write({
            'assigned_to': self.technician_id.id,
            'state': 'assigned',
        })
        (self.ticket_ids - submitted_tickets).write({
            'assigned_to': self.technician_id.id,
        })
        return {'type': 'ir.actions.act_window_close'}
