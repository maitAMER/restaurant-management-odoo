# -*- coding: utf-8 -*-
from odoo import fields, models


class RestaurantEquipmentMaintenance(models.Model):
    _name = 'restaurant.equipment.maintenance'
    _description = 'Restaurant Equipment Maintenance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, create_date desc, id desc'

    name = fields.Char(string='Ticket', required=True, default='New', tracking=True)
    equipment_id = fields.Many2one(
        'restaurant.equipment', string='Equipment', required=True,
        ondelete='restrict', index=True, tracking=True,
    )
    priority = fields.Selection(
        [
            ('0', 'Low'),
            ('1', 'Medium'),
            ('2', 'High'),
            ('3', 'Urgent'),
        ],
        string='Priority', required=True, default='1', tracking=True,
    )
    state = fields.Selection(
        [
            ('new', 'New'),
            ('in_progress', 'In Progress'),
            ('resolved', 'Resolved'),
        ],
        string='Status', required=True, default='new', tracking=True,
    )
    technician_id = fields.Many2one(
        'res.users', string='Assigned Technician', tracking=True,
    )
    description = fields.Text(string='Maintenance Description')
    request_date = fields.Date(string='Request Date', default=fields.Date.context_today)
    resolution_date = fields.Date(string='Resolution Date', tracking=True)

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_resolve(self):
        self.write({
            'state': 'resolved',
            'resolution_date': fields.Date.context_today(self),
        })
