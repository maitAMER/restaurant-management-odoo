# -*- coding: utf-8 -*-
{
    'name': "restaurant_management",

    'summary': "Manage restaurant menu items, customers, equipment, and maintenance",

    'description': "Restaurant menu, customer, equipment, and maintenance management.",

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    'category': 'Services/Restaurant',
    'version': '0.1',

    'depends': ['base', 'mail', 'product', 'crm', 'website'],
    

    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/menu_views.xml',
        'views/customer_views.xml',
        'views/equipment_views.xml',
        'views/equipment_maintenance_views.xml',
        'wizard/equipment_assign_wizard_views.xml',
        'views/reservation.xml',
        'views/tables.xml',
        'views/order_views.xml',
        'views/kitchen_views.xml',
        'views/driver_views.xml',
        'views/payment_views.xml',
        'views/crm_lead.xml',
        'views/website_templates.xml',
        'views/website_booking_templates.xml',
        'views/portal_template.xml',
        'views/menu.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
