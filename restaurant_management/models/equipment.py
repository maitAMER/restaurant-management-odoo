# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError


class RestaurantEquipment(models.Model):
    _name = 'restaurant.equipment'
    _description = 'Restaurant Equipment'
    _order = 'name, id'

    name = fields.Char(string='Equipment Name', required=True)
    serial_number = fields.Char(string='Serial Number / Barcode', copy=False, index=True)
    category = fields.Selection(
        [
            ('kitchen', 'Kitchen Equipment'),
            ('refrigeration', 'Refrigeration'),
            ('furniture', 'Furniture'),
            ('electrical', 'Electrical'),
            ('other', 'Other'),
        ],
        string='Equipment Category',
        required=True,
        default='kitchen',
    )
    equipment_type = fields.Selection(
        [
            ('oven', 'Oven'),
            ('fridge', 'Fridge'),
            ('dishwasher', 'Dishwasher'),
            ('pos_terminal', 'POS Terminal'),
            ('coffee_machine', 'Coffee Machine'),
            ('ac', 'Air Conditioner'),
            ('other', 'Other'),
        ],
        string='Equipment Type', default='other',
    )
    purchase_date = fields.Date(string='Purchase Date')
    warranty_expiry_date = fields.Date(string='Warranty Expiry Date')
    location = fields.Char(string='Restaurant Location')
    status = fields.Selection(
        [
            ('working', 'Working'),
            ('under_maintenance', 'Under Maintenance'),
            ('out_of_service', 'Out of Service'),
        ],
        string='Status',
        required=True,
        default='working',
    )
    maintenance_ids = fields.One2many(
        'restaurant.equipment.maintenance', 'equipment_id', string='Maintenance Tickets',
    )
    maintenance_count = fields.Integer(
        string='Maintenance Tickets', compute='_compute_maintenance_count',
    )

    _sql_constraints = [
        ('serial_number_unique', 'unique(serial_number)', 'The serial number must be unique.'),
    ]

    def _compute_maintenance_count(self):
        for equipment in self:
            equipment.maintenance_count = len(equipment.maintenance_ids)

    def _sync_maintenance_status(self):
        if not self:
            return
        active_equipment_ids = set(
            self.env['restaurant.equipment.maintenance'].sudo().search([
                ('equipment_id', 'in', self.ids),
                ('state', 'in', ['assigned', 'in_progress']),
            ]).mapped('equipment_id').ids
        )
        for equipment in self:
            if equipment.id in active_equipment_ids:
                new_status = 'under_maintenance'
            elif equipment.status == 'under_maintenance':
                new_status = 'working'
            else:
                continue
            if equipment.status != new_status:
                equipment.write({'status': new_status})

    def action_mark_out_of_service(self):
        self.ensure_one()
        if self.status == 'under_maintenance':
            raise UserError(
                'Complete or reassign the active maintenance ticket before '
                'marking this equipment out of service.'
            )
        self.write({'status': 'out_of_service'})

    def action_mark_working(self):
        self.ensure_one()
        active_ticket = self.env['restaurant.equipment.maintenance'].search_count([
            ('equipment_id', '=', self.id),
            ('state', 'in', ['assigned', 'in_progress']),
        ])
        if active_ticket:
            raise UserError(
                'This equipment has an active maintenance ticket and cannot be '
                'marked as working yet.'
            )
        self.write({'status': 'working'})

    def action_view_maintenance(self):
        self.ensure_one()
        action = self.env.ref(
            'restaurant_management.action_restaurant_equipment_maintenance'
        ).read()[0]
        action['domain'] = [('equipment_id', '=', self.id)]
        action['context'] = {'default_equipment_id': self.id}
        return action
