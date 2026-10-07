from odoo import models, fields


class RestaurantCustomer(models.Model):
    _name = 'restaurant.customer'
    _description = 'Restaurant Customer'

    name = fields.Char(string='Customer Name', required=True)
    phone = fields.Char(string='Phone Number')


class RestaurantPizzaCategory(models.Model):
    _name = 'restaurant.pizza.category'
    _description = 'Pizza Category'

    name = fields.Char(string='Category Name', required=True)


class RestaurantPizza(models.Model):
    _name = 'restaurant.pizza'
    _description = 'Restaurant Pizza'

    name = fields.Char(string='Pizza Name', required=True)
    price = fields.Float(string='Price', required=True)
    category_id = fields.Many2one('restaurant.pizza.category', string='Category')
    description = fields.Text(string='Description')


class RestaurantTable(models.Model):
    _name = 'restaurant.management.table'
    _description = 'Restaurant Table'

    name = fields.Char(string='Table Name', required=True)
    capacity = fields.Integer(string='Capacity')


class RestaurantChef(models.Model):
    _name = 'restaurant.chef'
    _description = 'Restaurant Chef'

    name = fields.Char(string='Chef Name', required=True)
    speciality = fields.Char(string='Speciality')


class RestaurantOrder(models.Model):
    _name = 'restaurant.order'
    _description = 'Restaurant Order'

    name = fields.Char(string='Order Reference', required=True, default='New')
    customer_id = fields.Many2one('restaurant.customer', string='Customer')
    total_amount = fields.Float(string='Total Amount')