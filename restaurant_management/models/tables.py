from odoo import models, fields


class RestaurantTable(models.Model):
    _name = 'restaurant.table'
    _description = 'Restaurant Table'
    _rec_name = 'name'
    _order = 'name asc'

    name = fields.Char(string='Table Name', required=True)

    capacity = fields.Integer(
        string='Capacity',
        required=True,
        default=2
    )

    location = fields.Selection([
        ('indoor', 'Indoor'),
        ('outdoor', 'Outdoor'),
        ('terrace', 'Terrace'),
        ('vip', 'VIP Section'),
    ], string='Location / Section', default='indoor', required=True)

    active = fields.Boolean(
        string='Active',
        default=True
    )
