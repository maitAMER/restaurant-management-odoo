# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import json
import calendar

# =========================
# API Response Helpers
# =========================

def valid_response(data=None, message='Success', status=200):
    return request.make_json_response({
        'status': 'success',
        'message': message,
        'data': data
    }, status=status)


def invalid_response(message='Bad Request', status=400, data=None):
    return request.make_json_response({
        'status': 'error',
        'message': message,
        'data': data
    }, status=status)


class RestaurantAPI(http.Controller):

    # ============================================================
    # CHECK API KEY
    # ============================================================
    @http.route(
        '/api/check_api_key',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False
    )
    def check_api_key(self):

        api_key = request.httprequest.headers.get(
            'Authorization',
            ''
        )

        api_key = api_key.replace('Bearer ', '').strip()

        user_id = request.env['res.users.apikeys']._check_credentials(
            scope='rpc',
            key=api_key
        )

        if not user_id:
            return invalid_response(
                message='Invalid API Key',
                status=401
            )

        return valid_response(
            message='Valid API Key',
            data={
                'user_id': user_id
            }
        )

    # ============================================================
    # 1. CREATE ORDER
    # ============================================================
    @http.route(
        '/api/restaurant/orders/create',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False
    )
    def create_order(self, **kwargs):

        TOKEN = '9476c9f36fa02d1de3e7f52aac13e038485b285f'

        authorization_token = request.httprequest.headers.get(
            'Authorization', ''
        )

        if authorization_token != f'Bearer {TOKEN}':
            return invalid_response(
                message='Unauthorized',
                status=401
            )

        try:
            params = request.httprequest.get_json(silent=True) or {}

            if not params.get('order_type') or not params.get('customer_id'):
                return invalid_response(
                    message='Order type and customer ID are required',
                    status=400
                )

            order_obj = request.env[
                'restaurant.order'
            ].sudo().create({
                'order_type': params.get('order_type'),
                'customer_id': params.get('customer_id'),
                'delivery_address': params.get('delivery_address'),
                'delivery_fee': params.get('delivery_fee', 0.0),
                'external_id': params.get('external_id'),
                'state': 'draft',
            })

            return valid_response(
                message='Order created successfully',
                data={
                    'order_id': order_obj.id,
                    'name': order_obj.name,
                    'external_id': order_obj.external_id
                }
            )

        except Exception as e:
            return invalid_response(
                message=str(e),
                status=500
            )

    # ============================================================
    # 2. GET ORDERS (Added back)
    # ============================================================
    @http.route(
        '/api/restaurant/orders',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False
    )
    def get_orders(self):

        TOKEN = '9476c9f36fa02d1de3e7f52aac13e038485b285f'
        authorization_token = request.httprequest.headers.get('Authorization', '')

        if authorization_token != f'Bearer {TOKEN}':
            return invalid_response(
                message='Unauthorized',
                status=401
            )

        try:
            orders = request.env[
                'restaurant.order'
            ].sudo().search([])

            return valid_response(
                message='Orders retrieved successfully',
                data=[{
                    'id': order.id,
                    'name': order.name,
                    'state': order.state,
                } for order in orders]
            )
        except Exception as e:
            return invalid_response(
                message=str(e),
                status=500
            )

    # ============================================================
    # 3. GET MONTHLY SALES
    # ============================================================
    @http.route(
        '/api/restaurant/sales/monthly',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False
    )
    def get_monthly_sales(self):

        year = request.httprequest.args.get('year')
        month = request.httprequest.args.get('month')

        if not year or not month:
            return invalid_response(
                message='Both year and month are required',
                status=400
            )

        try:
            year = int(year)
            month = int(month)
            
            if not (1 <= month <= 12):
                raise ValueError('Month must be between 1 and 12')

            last_day = calendar.monthrange(year, month)[1]
            
            date_from = f"{year:04d}-{month:02d}-01"
            date_to = f"{year:04d}-{month:02d}-{last_day:02d}"

            orders = request.env[
                'restaurant.order'
            ].sudo().search([
                ('create_date', '>=', f"{date_from} 00:00:00"),
                ('create_date', '<=', f"{date_to} 23:59:59"),
            ])

            total_sales = sum(orders.mapped('delivery_fee'))

            return valid_response(
                message=f'Sales for {year}-{month:02d} retrieved successfully',
                data={
                    'year': year,
                    'month': month,
                    'total_orders': len(orders),
                    'total_sales_amount': total_sales,
                    'orders': [{
                        'id': order.id,
                        'name': order.name,
                        'state': order.state,
                        'date': fields.Datetime.to_string(order.create_date),
                    } for order in orders]
                }
            )

        except ValueError as e:
            return invalid_response(
                message=str(e),
                status=400
            )
        except Exception as e:
            return invalid_response(
                message=str(e),
                status=500
            )



        # ============================================================
    # GET RESTAURANT MENU
    # ============================================================
    @http.route(
        '/api/restaurant/menu',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False
    )
    def get_menu(self):

        TOKEN = '9476c9f36fa02d1de3e7f52aac13e038485b285f'
        auth_header = request.httprequest.headers.get('Authorization', '')

    
        provided_token = auth_header.replace('Bearer ', '').strip()

        if provided_token != TOKEN:
            return invalid_response(message='Unauthorized', status=401)

        try:
           
            menu_items = request.env['restaurant.menu.item'].sudo().search([
                ('is_available', '=', True)
            ])

            menu_data = []
            for item in menu_items:
                menu_data.append({
                    'id': item.id,
                    'name': item.name,
                    'section': item.menu_section,
                    'section_display': dict(item._fields['menu_section'].selection).get(item.menu_section),
                    'price': item.price,
                    'size': item.size,
                    'pizza_type': item.pizza_type or '',
                    'ingredients': item.ingredients or '',
                    'description': item.description or '',
                    'prep_time_minutes': item.prep_time_minutes,
                    'daily_special': item.daily_special,
                    'allergens': item.allergens or '',
                })

            return valid_response(
                message='Menu retrieved successfully',
                data=menu_data
            )

        except Exception as e:
            return invalid_response(
                message=str(e),
                status=500
            )