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
        'views/menu_views.xml',
        'views/customer_views.xml',
        'views/menu.xml',
        'views/equipment_views.xml',
        'views/equipment_maintenance_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
