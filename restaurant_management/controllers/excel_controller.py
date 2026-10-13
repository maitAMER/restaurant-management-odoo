# -*- coding: utf-8 -*-
"""T083 - Export one order receipt to Excel."""
import io

import pytz

from odoo import http, _
from odoo.exceptions import AccessError
from odoo.http import request, content_disposition

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


COST_FIELD = 'cost'


class RestaurantExcelController(http.Controller):

    @http.route('/restaurant/order/<int:order_id>/receipt/excel',
                type='http', auth='user', methods=['GET'])
    def order_receipt_excel(self, order_id, **kwargs):
        
        if xlsxwriter is None:
            return request.make_response(_("xlsxwriter is not installed."), status=500)

        order = request.env['restaurant.order'].browse(order_id)
        if not order.exists():
            return request.not_found()
        try:  
            order.check_access_rights('read')
            order.check_access_rule('read')
        except AccessError:
            return request.make_response(_("Access denied."), status=403)

        env = request.env
        tz = pytz.timezone(env.user.tz or 'UTC')
        Payment = env['restaurant.payment']
        symbol = (env.company.currency_id.symbol or '').replace('"', '')

        type_label = dict(order._fields['order_type'].selection)
        state_label = dict(order._fields['state'].selection)
        method_label = dict(Payment._fields['method'].selection)
        ptype_label = dict(Payment._fields['payment_type'].selection)
        pstate_label = dict(Payment._fields['state'].selection)
        section_label = dict(env['restaurant.order.line']._fields['menu_section'].selection)

        payments = Payment.search([('order_id', '=', order.id)], order='payment_date')
        paid_rows = payments.filtered(lambda p: p.state == 'paid')
        paid_amount = sum(paid_rows.mapped('amount'))
        tips = sum(paid_rows.mapped('tip_amount'))
        balance = max(order.total_amount - paid_amount, 0.0)

        has_cost = COST_FIELD in env['restaurant.menu.item']._fields

        def unit_cost(product):
            return (product.sudo()[COST_FIELD] or 0.0) if has_cost else 0.0

        total_cost = sum(l.quantity * unit_cost(l.product_id) for l in order.order_line_ids)
        net = order.total_amount - total_cost

        # Workbook + formats 
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(
            output, {'in_memory': True, 'strings_to_formulas': False})
        worksheet = workbook.add_worksheet('Order Receipt')

        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#4472C4', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter'})
        title_format = workbook.add_format({
            'bold': True, 'font_size': 14, 'align': 'left'})
        label_format = workbook.add_format({
            'bold': True, 'bg_color': '#F2F2F2', 'border': 1})
        data_format = workbook.add_format({'border': 1})
        center_format = workbook.add_format({'border': 1, 'align': 'center'})
        qty_format = workbook.add_format({'border': 1, 'num_format': '#,##0.##', 'align': 'center'})
        currency_format = workbook.add_format({
            'num_format': '"%s" #,##0.00' % symbol, 'border': 1})
        total_label = workbook.add_format({
            'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        total_money = workbook.add_format({
            'bold': True, 'bg_color': '#D9E1F2', 'border': 1,
            'num_format': '"%s" #,##0.00' % symbol})
        due_money = workbook.add_format({
            'bold': True, 'font_color': '#C00000', 'bg_color': '#FDE9E7', 'border': 1,
            'num_format': '"%s" #,##0.00' % symbol})
        ok_money = workbook.add_format({
            'bold': True, 'font_color': '#1E7B34', 'bg_color': '#E6F4EA', 'border': 1,
            'num_format': '"%s" #,##0.00' % symbol})
        split_format = workbook.add_format({
            'border': 1, 'italic': True, 'font_color': '#595959'})
        split_money = workbook.add_format({
            'border': 1, 'italic': True, 'font_color': '#595959',
            'num_format': '"%s" #,##0.00' % symbol})
        datetime_format = workbook.add_format({
            'num_format': 'yyyy-mm-dd hh:mm', 'border': 1, 'align': 'center'})

        worksheet.set_column('A:A', 28)
        worksheet.set_column('B:B', 20)
        worksheet.set_column('C:C', 14)
        worksheet.set_column('D:E', 16)
        worksheet.set_column('F:F', 14)
        last_col = 5  

        def local(dt):
            return pytz.utc.localize(dt).astimezone(tz).replace(tzinfo=None)

        # Title
        row = 0
        worksheet.merge_range(row, 0, row, last_col,
                              'Order Receipt: %s' % (order.name or ''), title_format)
        row += 2

        # Order information
        worksheet.merge_range(row, 0, row, last_col, 'ORDER INFORMATION', header_format)
        row += 1
        info = [
            ('Order Reference', order.name or ''),
            ('Customer', order.customer_id.name or ''),
            ('Order Type', type_label.get(order.order_type, '')),
            ('Status', state_label.get(order.state, '')),
        ]
        for label, value in info:
            worksheet.write(row, 0, label, label_format)
            worksheet.merge_range(row, 1, row, 2, value, data_format)
            row += 1
        worksheet.write(row, 0, 'Order Date', label_format)
        if order.date_order:
            worksheet.merge_range(row, 1, row, 2, local(order.date_order), datetime_format)
        else:
            worksheet.merge_range(row, 1, row, 2, '', data_format)
        row += 1
        if order.notes:
            worksheet.write(row, 0, 'Notes', label_format)
            worksheet.merge_range(row, 1, row, last_col, order.notes, data_format)
            row += 1
        row += 1

        # Order items
        worksheet.merge_range(row, 0, row, last_col, 'ORDER ITEMS', header_format)
        row += 1
        for col, header in enumerate(['Item', 'Menu Section', 'Qty', 'Unit Price', 'Subtotal']
                                     + (['Cost'] if has_cost else [])):
            worksheet.write(row, col, header, header_format)
        row += 1
        for line in order.order_line_ids:
            worksheet.write(row, 0, line.product_id.name or '', data_format)
            worksheet.write(row, 1, section_label.get(line.menu_section, '') or '', data_format)
            worksheet.write(row, 2, line.quantity, qty_format)
            worksheet.write(row, 3, line.price_unit, currency_format)
            worksheet.write(row, 4, line.subtotal, currency_format)
            if has_cost:
                worksheet.write(row, 5, line.quantity * unit_cost(line.product_id), currency_format)
            row += 1
        row += 1

        # Totals
        worksheet.merge_range(row, 0, row, last_col, 'TOTALS', header_format)
        row += 1
        worksheet.write(row, 0, 'Order Total', total_label)
        worksheet.write(row, 1, order.total_amount, total_money)
        row += 1
        worksheet.write(row, 0, 'Paid', label_format)
        worksheet.write(row, 1, paid_amount, currency_format)
        row += 1
        worksheet.write(row, 0, 'Tips', label_format)
        worksheet.write(row, 1, tips, currency_format)
        row += 1
        worksheet.write(row, 0, 'Balance Due', label_format)
        worksheet.write(row, 1, balance, due_money if balance > 0 else ok_money)
        row += 2

        # Cost & profit
        if has_cost:
            worksheet.merge_range(row, 0, row, last_col, 'COST & PROFIT', header_format)
            row += 1
            worksheet.write(row, 0, 'Total Cost', label_format)
            worksheet.write(row, 1, total_cost, currency_format)
            row += 1
            worksheet.write(row, 0, 'NET LOSS' if net < 0 else 'NET PROFIT', total_label)
            worksheet.write(row, 1, net, due_money if net < 0 else ok_money)
            row += 2

        # Payment history
        if payments:
            worksheet.merge_range(row, 0, row, last_col, 'PAYMENT HISTORY', header_format)
            row += 1
            for col, header in enumerate(
                    ['Reference', 'Date', 'Type', 'Method', 'Amount', 'Status']):
                worksheet.write(row, col, header, header_format)
            row += 1
            for payment in payments:
                worksheet.write(row, 0, payment.name or '', data_format)
                if payment.payment_date:
                    worksheet.write_datetime(row, 1, local(payment.payment_date), datetime_format)
                else:
                    worksheet.write(row, 1, '', data_format)
                worksheet.write(row, 2, ptype_label.get(payment.payment_type, ''), center_format)
                worksheet.write(row, 3,
                                method_label.get(payment.method, '') if payment.payment_type == 'single' else 'Split',
                                center_format)
                worksheet.write(row, 4, payment.total_amount, currency_format)
                worksheet.write(row, 5, pstate_label.get(payment.state, ''), center_format)
                row += 1
                if payment.payment_type == 'split':
                    for split in payment.split_line_ids:
                        worksheet.write(row, 0, '', split_format)
                        worksheet.write(row, 1, '', split_format)
                        worksheet.write(row, 2, 'split line', split_format)
                        worksheet.write(row, 3, method_label.get(split.method, ''), split_format)
                        worksheet.write(row, 4, split.amount, split_money)
                        worksheet.write(row, 5, '', split_format)
                        row += 1

        worksheet.set_landscape()
        worksheet.fit_to_pages(1, 0)
        workbook.close()

        # Response
        output.seek(0)
        safe_name = (order.name or 'order').replace('/', '-').replace(' ', '_')
        filename = 'Receipt_%s.xlsx' % safe_name
        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type',
                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', content_disposition(filename)),
            ],
        )