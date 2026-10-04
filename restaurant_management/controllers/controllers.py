# -*- coding: utf-8 -*-
# from odoo import http


# class RestaurantManagement(http.Controller):
#     @http.route('/restaurant_management/restaurant_management', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/restaurant_management/restaurant_management/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('restaurant_management.listing', {
#             'root': '/restaurant_management/restaurant_management',
#             'objects': http.request.env['restaurant_management.restaurant_management'].search([]),
#         })

#     @http.route('/restaurant_management/restaurant_management/objects/<model("restaurant_management.restaurant_management"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('restaurant_management.object', {
#             'object': obj
#         })

