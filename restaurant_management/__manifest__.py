# -*- coding: utf-8 -*-
{
    'name': "restaurant_management",

    'summary': "Manage restaurant menu items, customers, equipment, and maintenance",

    'description': "Restaurant menu, customer, equipment, and maintenance management.",

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    'category': 'Services/Restaurant',
    'version': '0.1',

    'depends': ['base', 'mail'],

    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/menu_views.xml',
        'views/customer_views.xml',
        'views/equipment_views.xml',
        'views/equipment_maintenance_views.xml',
        'views/reservation.xml',
        'views/tables.xml',
        'views/menu.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
