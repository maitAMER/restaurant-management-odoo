# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from odoo import http, fields
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.addons.http_routing.models.ir_http import slug

class RestaurantWebsite(http.Controller):

    # 1. المنيو مع الفلترة حسب التصنيف وإخفاء الحساسية
    @http.route(['/menu', '/menu/page/<int:page>'], type='http', auth="public", website=True)
    def restaurant_menu(self, category_id=None, hide_allergens=None, **kwargs):
        domain = [('availability', '=', True)]
        if category_id:
            domain.append(('menu_section', '=', int(category_id)))
            
        categories = request.env['restaurant.menu.category'].sudo().search([])
        items = request.env['restaurant.menu.item'].sudo().search(domain)
        
        if hide_allergens:
            items = items.filtered(lambda i: not i.allergens or hide_allergens.lower() not in i.allergens.lower())

        return request.render('restaurant_management.menu_catalog_template', {
            'categories': categories,
            'items': items,
            'current_category': int(category_id) if category_id else None,
            'hide_allergens': hide_allergens,
        })

    # 2. مسار تفاصيل الصنف الفردي (/menu/<id>/<slug>)
    @http.route('/menu/<int:item_id>/<string:slug_str>', type='http', auth="public", website=True)
    def restaurant_item_detail(self, item_id, slug_str='', **kwargs):
        item = request.env['restaurant.menu.item'].sudo().search([
            ('id', '=', item_id),
            ('availability', '=', True),
        ], limit=1)
        if not item:
            return request.not_found()
        
        expected_slug = slug(item)
        if slug_str != expected_slug:
            return request.redirect(f'/menu/{item.id}/{expected_slug}', code=301)

        return request.render('restaurant_management.menu_item_detail_template', {
            'item': item,
        })

    # 3. مسار التحقق من إتاحة الطاولة عند الحجز (JSON Route)
    @http.route('/restaurant/reserve/check', type='json', auth="public", website=True)
    def check_table_reservation(self, table_id, reservation_time, duration_minutes=90, **kwargs):
        table = request.env['restaurant.table'].sudo().browse(int(table_id))
        if not table.exists():
            return {'status': 'error', 'message': 'Table not found'}

        try:
            start = datetime.fromisoformat(reservation_time)
            duration_minutes = int(duration_minutes)
            if duration_minutes <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return {'status': 'error', 'message': 'Invalid reservation time or duration'}

        end = start + timedelta(minutes=duration_minutes)
        is_available = table.is_available_for_period(start, end)
        return {'available': is_available}

    # 4. مسار صفحة حجز الطاولات
    @http.route('/restaurant/reserve', type='http', auth="public", website=True)
    def restaurant_reserve_page(self, **kwargs):
        tables = request.env['restaurant.table'].sudo().search([])
        return request.render('restaurant_management.table_reservation_template', {
            'tables': tables,
        })

    # 5. إرسال طلب حجز الطاولة الفعلي وإنشاء Draft Order
    @http.route('/restaurant/reserve/submit', type='http', auth="public", methods=['POST'], website=True, csrf=True)
    def restaurant_reserve_submit(self, **post):
        table_id = int(post.get('table_id'))
        reservation_time = post.get('reservation_time')
        duration_minutes = int(post.get('duration_minutes', 90))
        customer_name = post.get('customer_name')
        customer_email = post.get('customer_email')

        try:
            reservation_datetime = datetime.fromisoformat(reservation_time)
        except (TypeError, ValueError):
            return request.redirect('/restaurant/reserve?error=invalid_time')
        
        table = request.env['restaurant.table'].sudo().browse(table_id)
        if not table.exists():
            return request.redirect('/restaurant/reserve?error=table_not_found')
        
        if duration_minutes <= 0:
            return request.redirect('/restaurant/reserve?error=invalid_time')

        reservation_end = reservation_datetime + timedelta(minutes=duration_minutes)
        if not table.is_available_for_period(reservation_datetime, reservation_end):
            return request.redirect('/restaurant/reserve?error=table_busy')

        customer = request.env['restaurant.customer'].sudo().search([('email', '=', customer_email)], limit=1)
        if not customer:
            customer = request.env['restaurant.customer'].sudo().create({
                'name': customer_name,
                'email': customer_email,
            })

        try:
            request.env['restaurant.reservation'].sudo().create({
                'reservation_date': fields.Datetime.to_string(reservation_datetime),
                'duration': duration_minutes / 60.0,
                'table_id': table_id,
                'customer_id': customer.id,
            })

            order_vals = {
                'customer_id': request.env.user.partner_id.id,
                'restaurant_customer_id': customer.id,
                'table_id': table_id,
                'order_type': 'dine_in',
                'state': 'draft',
                'date_order': fields.Datetime.to_string(reservation_datetime),
                'notes': f"Table Reservation for {customer_name} (Table: {table.name})"
            }
            request.env['restaurant.order'].sudo().create(order_vals)

        except ValidationError:
            return request.redirect('/restaurant/reserve?error=table_busy')

        return request.render('restaurant_management.reservation_success_template', {})

    # 6. مسار إرسال الأوردر السريع من المنيو أو صفحة تفاصيل الصنف (ينزل Draft Order)
    @http.route('/restaurant/order/submit', type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def submit_website_order(self, menu_item_id, quantity=1, **kwargs):
        user = request.env.user
        partner = user.partner_id
        is_public_user = user._is_public()
        customer_model = request.env['restaurant.customer'].sudo()
        customer = customer_model.browse()

        if is_public_user:
            guest_cust_id = request.session.get('restaurant_guest_customer_id')
            if guest_cust_id:
                customer = customer_model.browse(guest_cust_id).exists()
        else:
            customer = customer_model.search([('user_id', '=', user.id)], limit=1)
            email = (partner.email or '').strip().casefold()
            if not customer and email:
                customer = customer_model.search([('email_normalized', '=', email)], limit=1)

        if not customer:
            customer_vals = {
                'name': partner.name if not is_public_user and partner.name else 'Website Guest',
            }
            if not is_public_user:
                customer_vals['user_id'] = user.id
                if partner.email:
                    customer_vals['email'] = partner.email.strip()
            customer = customer_model.create(customer_vals)

        menu_item = request.env['restaurant.menu.item'].sudo().browse(int(menu_item_id))

        # تم ضبط customer_id بحيث لا يسبب مشكلة Access Denied مع الـ Public User
        order = request.env['restaurant.order'].sudo().create({
            'customer_id': partner.id if not is_public_user else False,
            'restaurant_customer_id': customer.id,
            'order_type': 'takeaway',
            'state': 'draft',
            'line_ids': [(0, 0, {
                'menu_item_id': int(menu_item_id),
                'quantity': int(quantity),
                'unit_price': menu_item.price if menu_item else 0.0,
            })]
        })

        if is_public_user:
            guest_order_ids = request.session.get('restaurant_guest_order_ids', [])
            request.session['restaurant_guest_order_ids'] = list(set(guest_order_ids + [order.id]))
            request.session['restaurant_guest_customer_id'] = customer.id

        return request.redirect('/my/orders')

    # 7. مسار استفسارات الحفلات والكاترينج (تظهر فوراً في الـ CRM Pipeline)
    @http.route('/restaurant/catering', type='http', auth="public", website=True)
    def restaurant_catering_page(self, **kwargs):
        categories = request.env['restaurant.menu.category'].sudo().search([])
        return request.render('restaurant_management.catering_inquiry_template', {
            'categories': categories,
        })

    @http.route('/restaurant/catering/submit', type='http', auth="public", methods=['POST'], website=True, csrf=True)
    def restaurant_catering_submit(self, **post):
        name = post.get('name')
        email = post.get('email')
        phone = post.get('phone')
        description = post.get('description')
        guest_count = post.get('guest_count')
        category_id = post.get('category_id')

        first_stage = request.env['crm.stage'].sudo().search([], order='sequence asc', limit=1)

        lead_vals = {
            'name': f"Catering Inquiry - {name} ({guest_count} Guests)",
            'contact_name': name,
            'email_from': email,
            'phone': phone,
            'description': description,
            'type': 'opportunity',
            'stage_id': first_stage.id if first_stage else False,
            'lead_source': 'website',
        }
        
        if category_id and category_id.isdigit():
            lead_vals['menu_category_id'] = int(category_id)

        request.env['crm.lead'].sudo().create(lead_vals)

        return request.render('restaurant_management.catering_success_template', {})

    # 8. مسار بوابة العميل لعرض أوردراته ونقاط الولاء
    @http.route(['/my/orders', '/my/orders/page/<int:page>'], type='http', auth="public", website=True)
    def portal_my_orders(self, **kwargs):
        customer_model = request.env['restaurant.customer'].sudo()
        order_model = request.env['restaurant.order'].sudo()

        if request.env.user._is_public():
            customer = customer_model.browse(
                request.session.get('restaurant_guest_customer_id')
            ).exists()
            guest_order_ids = request.session.get('restaurant_guest_order_ids', [])
            orders = order_model.search([
                ('id', 'in', guest_order_ids),
                ('restaurant_customer_id', '=', customer.id),
            ]) if customer else order_model.browse()
        else:
            partner = request.env.user.partner_id
            email = (partner.email or '').strip().casefold()
            customer = customer_model.search([
                '|',
                ('user_id', '=', request.env.user.id),
                ('email_normalized', '=', email),
            ], limit=1)
            orders = order_model.search([
                ('restaurant_customer_id', '=', customer.id)
            ]) if customer else order_model.browse()

        return request.render('restaurant_management.portal_my_orders_template', {
            'orders': orders,
            'loyalty_points': customer.sudo().loyalty_points if customer else 0,
            'page_name': 'order',
        })