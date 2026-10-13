# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class RestaurantEquipmentMaintenance(models.Model):
    _name = 'restaurant.equipment.maintenance'
    _description = 'Restaurant Equipment Maintenance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'urgency desc, create_date desc, id desc'

    name = fields.Char(string='Ticket', required=True, default='New', tracking=True)
    equipment_id = fields.Many2one(
        'restaurant.equipment', string='Equipment', required=True,
        ondelete='restrict', index=True, tracking=True,
    )
    equipment_type = fields.Selection(
        related='equipment_id.equipment_type', string='Equipment Type', store=True,
    )
    priority = fields.Selection(
        [
            ('0', 'Low'),
            ('1', 'Medium'),
            ('2', 'High'),
            ('3', 'Urgent'),
        ],
        string='Legacy Priority', required=True, default='1', tracking=True,
    )
    urgency = fields.Selection(
        [
            ('0', 'Low'),
            ('1', 'Medium'),
            ('2', 'High'),
            ('3', 'Urgent'),
        ],
        string='Urgency', default='1', tracking=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('assigned', 'Assigned'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status', required=True, default='submitted', tracking=True,
    )
    technician_id = fields.Many2one(
        'res.users', string='Assigned Technician', tracking=True,
    )
    assigned_to = fields.Many2one(
        'res.users', related='technician_id', string='Assigned To',
        readonly=False, store=True,
    )
    description = fields.Text(string='Maintenance Description')
    request_date = fields.Date(string='Request Date', default=fields.Date.context_today)
    scheduled_date = fields.Date(string='Scheduled Date')
    resolution_date = fields.Date(string='Resolution Date', tracking=True)
    completed_date = fields.Date(
        related='resolution_date', string='Completed Date', readonly=False,
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    actual_cost = fields.Monetary(
        string='Actual Repair Cost', currency_field='currency_id',
        required=True, default=0.0,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name') in (False, 'New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'restaurant.equipment.maintenance'
                ) or 'New'
            vals.setdefault('urgency', vals.get('priority') or '1')
            vals.setdefault('priority', vals.get('urgency') or '1')
        tickets = super().create(vals_list)
        tickets.mapped('equipment_id')._sync_maintenance_status()
        return tickets

    def write(self, vals):
        affected_equipment = self.mapped('equipment_id')
        result = super().write(vals)
        affected_equipment |= self.mapped('equipment_id')
        affected_equipment._sync_maintenance_status()
        return result

    def unlink(self):
        affected_equipment = self.mapped('equipment_id')
        result = super().unlink()
        affected_equipment._sync_maintenance_status()
        return result

    def action_open_assign_wizard(self):
        self.ensure_one()
        action = self.env.ref(
            'restaurant_management.action_restaurant_equipment_assign_wizard'
        ).read()[0]
        action['context'] = {
            **self.env.context,
            'active_model': self._name,
            'active_ids': self.ids,
            'active_id': self.id,
        }
        return action

    def action_start(self):
        if any(ticket.state != 'assigned' for ticket in self):
            raise UserError('Only assigned tickets can be started.')
        if any(not ticket.technician_id for ticket in self):
            raise UserError('Assign a technician before starting the repair.')
        self.write({'state': 'in_progress'})

    def action_submit(self):
        if any(ticket.state != 'draft' for ticket in self):
            raise UserError('Only draft tickets can be submitted.')
        self.write({'state': 'submitted'})

    def action_cancel(self):
        if any(ticket.state in ('done', 'cancelled') for ticket in self):
            raise UserError('Completed or cancelled tickets cannot be cancelled again.')
        self.write({'state': 'cancelled'})

    def action_done(self):
        if any(ticket.state != 'in_progress' for ticket in self):
            raise UserError('Only tickets in progress can be marked done.')
        self.write({
            'state': 'done',
            'resolution_date': fields.Date.context_today(self),
        })

    @api.constrains('actual_cost')
    def _check_actual_cost_nonnegative(self):
        if any(ticket.actual_cost < 0 for ticket in self):
            raise ValidationError('Actual repair cost cannot be negative.')
