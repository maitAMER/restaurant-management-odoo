# -*- coding: utf-8 -*-
import base64
import io
from collections import OrderedDict
from datetime import datetime, time

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

try:
    import xlsxwriter
except ImportError:  
    xlsxwriter = None

COST_FIELD = 'cost'


class SalesReportWizardLine(models.TransientModel):
    """One preview row = one day of sales."""
    _name = 'restaurant.sales_report_wizard.line'
    _description = 'Sales Report Preview Line'
    _order = 'date'

    wizard_id = fields.Many2one('restaurant.sales_report_wizard',
                                required=True, ondelete='cascade')
    date = fields.Date()
    order_count = fields.Integer(string='Orders')
    total_amount = fields.Float(string='Sales')
    cost = fields.Float(string='Cost')
    profit = fields.Float(string='Profit / Loss')


class SalesReportWizard(models.TransientModel):
    """T081 - Period sales report with on-screen preview.
       T082 - Excel export (xlsxwriter) from the same wizard."""
    _name = 'restaurant.sales_report_wizard'
    _description = 'Sales Report Wizard'

    date_from = fields.Date(
        string='From', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(
        string='To', required=True,
        default=lambda self: fields.Date.context_today(self))
    order_type = fields.Selection(
        [('all', 'All types'), ('dine_in', 'Dine In'),
         ('takeaway', 'Takeaway'), ('delivery', 'Delivery')],
        string='Order Type', default='all', required=True)

    line_ids = fields.One2many('restaurant.sales_report_wizard.line',
                               'wizard_id', string='Daily Sales')
    total_orders = fields.Integer(readonly=True)
    total_sales = fields.Float(readonly=True)
    total_cost = fields.Float(string='Total Cost', readonly=True)
    net_profit = fields.Float(string='Net Profit', readonly=True)
    net_loss = fields.Float(string='Net Loss', readonly=True)
    total_tips = fields.Float(readonly=True)
    average_order = fields.Float(readonly=True)
    previewed = fields.Boolean(readonly=True)

    excel_file = fields.Binary(readonly=True, attachment=False)
    excel_filename = fields.Char(readonly=True)

    # ------------------------------------------------------------------
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wiz in self:
            if wiz.date_from and wiz.date_to and wiz.date_from > wiz.date_to:
                raise ValidationError(_("'From' date must be before or equal to 'To' date."))

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def _user_tz(self):
        return pytz.timezone(self.env.user.tz or 'UTC')

    def _period_bounds(self):
        """Local date range -> naive UTC datetimes for the DB domain."""
        tz = self._user_tz()
        start = tz.localize(datetime.combine(self.date_from, time.min))
        end = tz.localize(datetime.combine(self.date_to, time.max))
        return (start.astimezone(pytz.utc).replace(tzinfo=None),
                end.astimezone(pytz.utc).replace(tzinfo=None))

    def _get_orders(self):
        """Delivered orders in the period (your 'delivered' = finished/sold)."""
        self.ensure_one()
        start, end = self._period_bounds()
        domain = [
            ('state', '=', 'completed'),
            ('date_order', '>=', start),
            ('date_order', '<=', end),
        ]
        if self.order_type != 'all':
            domain.append(('order_type', '=', self.order_type))
        return self.env['restaurant.order'].search(domain, order='date_order')

    def _local_date(self, dt):
        return pytz.utc.localize(dt).astimezone(self._user_tz()).date()

    def _check_cost_field(self):
        if COST_FIELD not in self.env['restaurant.menu.item']._fields:
            raise UserError(_(
                "The menu item model has no field named '%s'.\n"
                "Set COST_FIELD at the top of wizard/sales_report_wizard.py "
                "to the name of your cost field.", COST_FIELD))

    def _unit_cost(self, product):
        # sudo: the cost field may be restricted to managers
        return product.sudo()[COST_FIELD] or 0.0

    def _order_cost(self, order):
        return sum(l.quantity * self._unit_cost(l.menu_item_id)
                   for l in order.line_ids)

    def _compute_report(self):
        """Fill the preview lines and the totals."""
        self.ensure_one()
        self._check_cost_field()
        orders = self._get_orders()

        days = OrderedDict()
        total_cost = 0.0
        for o in orders:
            d = self._local_date(o.date_order)
            cost = self._order_cost(o)
            row = days.setdefault(d, dict(order_count=0, total_amount=0.0, cost=0.0))
            row['order_count'] += 1
            row['total_amount'] += o.total_amount
            row['cost'] += cost
            total_cost += cost

        paid_payments = self.env['restaurant.payment'].search([
            ('order_id', 'in', orders.ids), ('state', '=', 'paid')])
        tips = sum(paid_payments.mapped('tip_amount'))

        self.line_ids.unlink()
        self.env['restaurant.sales_report_wizard.line'].create([
            dict(wizard_id=self.id, date=d,
                 profit=vals['total_amount'] - vals['cost'], **vals)
            for d, vals in days.items()])

        total_sales = sum(orders.mapped('total_amount'))
        net = total_sales - total_cost
        self.write({
            'total_orders': len(orders),
            'total_sales': total_sales,
            'total_cost': total_cost,
            'net_profit': max(net, 0.0),
            'net_loss': max(-net, 0.0),
            'total_tips': tips,
            'average_order': total_sales / len(orders) if orders else 0.0,
            'previewed': True,
        })
        return orders

    def _top_items(self, orders, limit=15):
        items = {}
        for line in orders.mapped('line_ids'):
            name = line.menu_item_id.name or _('(unknown)')
            rec = items.setdefault(name, [0.0, 0.0])
            rec[0] += line.quantity
            rec[1] += line.price_subtotal
        return sorted(items.items(), key=lambda kv: kv[1][1], reverse=True)[:limit]

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_preview(self):
        self.ensure_one()
        self._compute_report()
        return self._reopen()

    def action_export_excel(self):
        self.ensure_one()
        orders = self._compute_report()
        data = self._build_xlsx(orders)
        self.write({
            'excel_file': base64.b64encode(data),
            'excel_filename': 'sales_report_%s_%s.xlsx' % (self.date_from, self.date_to),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': ('/web/content/?model=%s&id=%s&field=excel_file'
                    '&filename_field=excel_filename&download=true') % (self._name, self.id),
            'target': 'self',
        }

    
    # Excel 
    
    def _build_xlsx(self, orders):
        self.ensure_one()
        if xlsxwriter is None:
            raise ValidationError(_("The Python package 'xlsxwriter' is not installed."))

        symbol = (self.env.company.currency_id.symbol or '').replace('"', '')
        money_fmt = '"%s" #,##0.00;[Red]-"%s" #,##0.00' % (symbol, symbol)
        type_label = dict(self._fields['order_type'].selection)
        net = self.total_sales - self.total_cost
        is_loss = net < 0

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(
            output, {'in_memory': True, 'strings_to_formulas': False})

        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#4472C4', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter'})
        title_format = workbook.add_format({
            'bold': True, 'font_size': 16, 'align': 'left', 'valign': 'vcenter'})
        label_format = workbook.add_format({
            'bold': True, 'bg_color': '#F2F2F2', 'border': 1})
        data_format = workbook.add_format({'border': 1})
        center_format = workbook.add_format({'border': 1, 'align': 'center'})
        number_format = workbook.add_format({'border': 1, 'num_format': '#,##0.##', 'align': 'center'})
        currency_format = workbook.add_format({'border': 1, 'num_format': money_fmt})
        date_format = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd', 'align': 'center'})
        datetime_format = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd hh:mm', 'align': 'center'})
        total_label = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        total_number = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1,
                                            'num_format': '#,##0.##', 'align': 'center'})
        total_money = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1,
                                           'num_format': money_fmt})
        paid_format = workbook.add_format({'border': 1, 'align': 'center',
                                           'font_color': '#1E7B34', 'bg_color': '#E6F4EA'})
        unpaid_format = workbook.add_format({'border': 1, 'align': 'center',
                                             'font_color': '#C00000', 'bg_color': '#FDE9E7'})
        profit_label = workbook.add_format({
            'bold': True, 'border': 1,
            'font_color': '#C00000' if is_loss else '#1E7B34',
            'bg_color': '#FDE9E7' if is_loss else '#E6F4EA'})
        profit_money = workbook.add_format({
            'bold': True, 'border': 1, 'num_format': money_fmt,
            'font_color': '#C00000' if is_loss else '#1E7B34',
            'bg_color': '#FDE9E7' if is_loss else '#E6F4EA'})

        # report 
        ws = workbook.add_worksheet('Sales Report')
        ws.set_column('A:A', 30)
        ws.set_column('B:E', 18)
        last = 4
        row = 0
        ws.set_row(0, 26)
        ws.merge_range(row, 0, row, last, 'Sales Report', title_format)
        row += 2

        ws.merge_range(row, 0, row, last, 'REPORT INFORMATION', header_format)
        row += 1
        for label, value in [
            ('Period', '%s  to  %s' % (self.date_from, self.date_to)),
            ('Order Type', type_label.get(self.order_type, 'All types')),
            ('Generated By', self.env.user.name),
        ]:
            ws.write(row, 0, label, label_format)
            ws.merge_range(row, 1, row, last, value, data_format)
            row += 1
        row += 1

        ws.merge_range(row, 0, row, last, 'SUMMARY', header_format)
        row += 1
        for label, value, fmt in [
            ('Delivered Orders', self.total_orders, number_format),
            ('Total Sales', self.total_sales, currency_format),
            ('Total Cost', self.total_cost, currency_format),
        ]:
            ws.write(row, 0, label, label_format)
            ws.merge_range(row, 1, row, 2, value, fmt)
            row += 1
        ws.write(row, 0, 'NET LOSS' if is_loss else 'NET PROFIT', profit_label)
        ws.merge_range(row, 1, row, 2, net, profit_money)
        row += 1
        for label, value in [('Tips Collected', self.total_tips),
                             ('Average Order Value', self.average_order)]:
            ws.write(row, 0, label, label_format)
            ws.merge_range(row, 1, row, 2, value, currency_format)
            row += 1
        row += 1

        ws.merge_range(row, 0, row, last, 'DAILY SALES', header_format)
        row += 1
        for col, h in enumerate(['Date', 'Orders', 'Sales', 'Cost', 'Profit / Loss']):
            ws.write(row, col, h, header_format)
        row += 1
        day_orders = day_sales = day_cost = 0
        for line in self.line_ids.sorted('date'):
            ws.write_datetime(row, 0, datetime.combine(line.date, time.min), date_format)
            ws.write(row, 1, line.order_count, number_format)
            ws.write(row, 2, line.total_amount, currency_format)
            ws.write(row, 3, line.cost, currency_format)
            ws.write(row, 4, line.profit, currency_format)
            day_orders += line.order_count
            day_sales += line.total_amount
            day_cost += line.cost
            row += 1
        ws.write(row, 0, 'TOTAL', total_label)
        ws.write(row, 1, day_orders, total_number)
        ws.write(row, 2, day_sales, total_money)
        ws.write(row, 3, day_cost, total_money)
        ws.write(row, 4, day_sales - day_cost, total_money)
        row += 2

        ws.merge_range(row, 0, row, last, 'TOP SELLING ITEMS', header_format)
        row += 1
        for col, h in enumerate(['Item', 'Quantity', 'Revenue']):
            ws.write(row, col, h, header_format)
        row += 1
        for name, (qty, rev) in self._top_items(orders):
            ws.write(row, 0, name, data_format)
            ws.write(row, 1, qty, number_format)
            ws.write(row, 2, rev, currency_format)
            row += 1

        ws.set_landscape()
        ws.fit_to_pages(1, 0)

        # orders 
        paid_order_ids = set(self.env['restaurant.payment'].search([
            ('order_id', 'in', orders.ids), ('state', '=', 'paid')]).mapped('order_id').ids)
        wo = workbook.add_worksheet('Orders')
        wo.set_column('A:A', 16)
        wo.set_column('B:B', 18)
        wo.set_column('C:C', 28)
        wo.set_column('D:H', 16)
        wo.merge_range(0, 0, 0, 7, 'ORDERS IN PERIOD', header_format)
        for col, h in enumerate(['Order', 'Date', 'Customer', 'Type', 'Sales',
                                 'Cost', 'Profit / Loss', 'Payment']):
            wo.write(1, col, h, header_format)
        r = 2
        sum_sales = sum_cost = 0.0
        for o in orders:
            local_dt = pytz.utc.localize(o.date_order).astimezone(self._user_tz()).replace(tzinfo=None)
            is_paid = o.id in paid_order_ids
            cost = self._order_cost(o)
            sum_sales += o.total_amount
            sum_cost += cost
            wo.write(r, 0, o.name or '', data_format)
            wo.write_datetime(r, 1, local_dt, datetime_format)
            wo.write(r, 2, o.customer_id.name or '', data_format)
            wo.write(r, 3, type_label.get(o.order_type, ''), center_format)
            wo.write(r, 4, o.total_amount, currency_format)
            wo.write(r, 5, cost, currency_format)
            wo.write(r, 6, o.total_amount - cost, currency_format)
            wo.write(r, 7, 'Paid' if is_paid else 'Unpaid', paid_format if is_paid else unpaid_format)
            r += 1
        wo.write(r, 0, 'TOTAL', total_label)
        for c in (1, 2, 3):
            wo.write(r, c, '', total_label)
        wo.write(r, 4, sum_sales, total_money)
        wo.write(r, 5, sum_cost, total_money)
        wo.write(r, 6, sum_sales - sum_cost, total_money)
        wo.write(r, 7, '', total_label)
        wo.freeze_panes(2, 0)
        wo.set_landscape()
        wo.fit_to_pages(1, 0)

        workbook.close()
        return output.getvalue()