# -*- coding: utf-8 -*-
from odoo import fields, models


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

    def action_view_maintenance(self):
        self.ensure_one()
        action = self.env.ref(
            'restaurant_management.action_restaurant_equipment_maintenance'
        ).read()[0]
        action['domain'] = [('equipment_id', '=', self.id)]
        action['context'] = {'default_equipment_id': self.id}
        return action
