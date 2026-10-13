# -*- coding: utf-8 -*-
from datetime import datetime
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
        
        is_available = True
        if hasattr(table, 'is_available_for_period'):
            is_available = table.is_available_for_period(reservation_time, int(duration_minutes))
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
        
        # التأكد من الإتاحة
        if hasattr(table, 'is_available_for_period') and not table.is_available_for_period(reservation_time, duration_minutes):
            return request.redirect('/restaurant/reserve?error=table_busy')

        # البحث أو إنشاء العميل
        customer = request.env['restaurant.customer'].sudo().search([('email', '=', customer_email)], limit=1)
        if not customer:
            customer = request.env['restaurant.customer'].sudo().create({
                'name': customer_name,
                'email': customer_email,
            })

        try:
            # 1. إنشاء الحجز في جدول الحجوزات
            request.env['restaurant.reservation'].sudo().create({
                'reservation_date': fields.Datetime.to_string(reservation_datetime),
                'duration': duration_minutes / 60.0,
                'table_id': table_id,
                'customer_id': customer.id,
            })

            # 2. إنشاء Draft Order مربوط بالطاولة والعميل
            request.env['restaurant.order'].sudo().create({
                'customer_id': customer.id,
                'table_id': table_id,
                'order_type': 'dine_in',
                'state': 'draft',
                'date_order': fields.Datetime.to_string(reservation_datetime),
                'notes': f"Table Reservation for {customer_name} (Table: {table.name})"
            })

        except ValidationError:
            return request.redirect('/restaurant/reserve?error=table_busy')

        return request.render('restaurant_management.reservation_success_template', {})

    # 6. مسار استفسارات الحفلات والكاترينج (تظهر فوراً في الـ CRM Pipeline)
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

        # الحصول على أول مرحلة في الـ Pipeline لتظهر تحت عمود New مباشرة
        first_stage = request.env['crm.stage'].sudo().search([], order='sequence asc', limit=1)

        lead_vals = {
            'name': f"Catering Inquiry - {name} ({guest_count} Guests)",
            'contact_name': name,
            'email_from': email,
            'phone': phone,
            'description': description,
            'type': 'opportunity',  # تحويلها لـ opportunity لكي تظهر في الـ Pipeline Canvas
            'stage_id': first_stage.id if first_stage else False,
            'lead_source': 'website',
        }
        
        if category_id and category_id.isdigit():
            lead_vals['menu_category_id'] = int(category_id)

        request.env['crm.lead'].sudo().create(lead_vals)

        return request.render('restaurant_management.catering_success_template', {})