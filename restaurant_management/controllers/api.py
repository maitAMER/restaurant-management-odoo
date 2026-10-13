# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request

class RestaurantAPI(http.Controller):

    @http.route('/api/restaurant/login', type='json', auth='none', methods=['POST'], csrf=False)
    def api_login(self, **kwargs):
        data = request.jsonrequest
        token_str = data.get('token')
        if not token_str:
            return {'status': 'error', 'message': 'Token is required'}
        
        token = request.env['restaurant.api_token'].sudo().search([('token', '=', token_str)], limit=1)
        if not token:
            return {'status': 'error', 'message': 'Invalid token'}
        
        return {'status': 'success', 'user_id': token.user_id.id}

    @http.route('/api/restaurant/orders/create', type='json', auth='user', methods=['POST'], csrf=False)
    def api_create_order(self, **kwargs):
        data = request.jsonrequest
        external_id = data.get('external_id')
        
        existing_order = request.env['restaurant.order'].search([('external_id', '=', external_id)], limit=1)
        if existing_order:
            return {'status': 'success', 'order_id': existing_order.id, 'message': 'Order already exists'}
        
        values = {
            'external_id': external_id,
            'order_type': data.get('order_type', 'delivery'),
            'customer_id': data.get('customer_id'),
            'delivery_address': data.get('delivery_address'),
            'delivery_fee': data.get('delivery_fee', 0.0),
        }
        order = request.env['restaurant.order'].create(values)
        return {'status': 'success', 'order_id': order.id}