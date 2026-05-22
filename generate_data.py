#!/usr/bin/env python3
"""Generate data.json for Bismillah Traders dashboard from Odoo XML-RPC."""
import xmlrpc.client, ssl, json, sys
from datetime import datetime, timedelta, date
from collections import defaultdict
from calendar import monthrange

ssl._create_default_https_context = ssl._create_unverified_context

URL = 'https://odoo-ss6o.srv1069133.hstgr.cloud'
DB = 'kitchen_dunya'
USER = 'msme.rs786@gmail.com'
PASS = 'sales.kitchendunya53'

def connect():
    common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
    uid = common.authenticate(DB, USER, PASS, {})
    models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')
    return uid, models

def get_inventory_valuation(uid, models):
    """Get total inventory value and breakdown by product/category."""
    products = models.execute_kw(DB, uid, PASS, 'product.product', 'search_read',
        [[['qty_available', '>', 0]]],
        {'fields': ['id', 'name', 'default_code', 'qty_available', 'standard_price', 'categ_id']})
    
    total_value = 0
    by_category = defaultdict(lambda: {'qty': 0, 'value': 0, 'items': 0})
    cat_names = {}
    items = []
    
    for p in products:
        qty = p['qty_available'] or 0
        cost = p['standard_price'] or 0
        value = qty * cost
        total_value += value
        
        cat_id = p['categ_id'][0] if p.get('categ_id') else 0
        cat_name = p['categ_id'][1] if p.get('categ_id') else 'Uncategorized'
        cat_names[cat_id] = cat_name
        by_category[cat_id]['qty'] += qty
        by_category[cat_id]['value'] += value
        by_category[cat_id]['items'] += 1
        
        items.append({
            'name': p['name'],
            'sku': p.get('default_code', '') or '',
            'qty': round(qty),
            'cost': round(cost),
            'value': round(value)
        })
    
    items.sort(key=lambda x: x['value'], reverse=True)
    
    categories = []
    for cat_id, data in sorted(by_category.items(), key=lambda x: x[1]['value'], reverse=True):
        categories.append({
            'name': cat_names.get(cat_id, f'ID {cat_id}'),
            'items': data['items'],
            'qty': round(data['qty']),
            'value': round(data['value']),
            'pct': round(data['value'] / total_value * 100, 1) if total_value else 0
        })
    
    return {
        'total_value': round(total_value),
        'total_items': len(items),
        'total_units': sum(i['qty'] for i in items),
        'top_product': items[0] if items else None,
        'products': items,
        'categories': categories
    }


def get_cashflow_forecast(uid, models):
    """Get cash flow forecast based on pending invoices."""
    today = datetime.now()
    cutoff = today + timedelta(days=30)
    
    def get_company_name(cid):
        if not cid: return 'Unknown'
        c = models.execute_kw(DB, uid, PASS, 'res.company', 'read', [cid[0], ['name']])
        return c[0]['name']
    
    # Customer invoices (money in) — posted, not paid, due within 30 days
    customer_invoices = models.execute_kw(DB, uid, PASS, 'account.move', 'search_read',
        [[['move_type', '=', 'out_invoice'],
          ['state', '=', 'posted'],
          ['payment_state', 'in', ['not_paid', 'partial']],
          ['invoice_date_due', '<=', cutoff.strftime('%Y-%m-%d')]]],
        {'fields': ['name', 'partner_id', 'amount_total', 'amount_residual',
                    'invoice_date', 'invoice_date_due', 'company_id', 'amount_residual_signed']})
    
    # All customer invoices (for total outstanding)
    all_customer = models.execute_kw(DB, uid, PASS, 'account.move', 'search_read',
        [[['move_type', '=', 'out_invoice'],
          ['state', '=', 'posted'],
          ['payment_state', 'in', ['not_paid', 'partial']]]],
        {'fields': ['name', 'partner_id', 'amount_total', 'amount_residual',
                    'invoice_date', 'invoice_date_due', 'company_id', 'amount_residual_signed']})
    
    # Vendor bills (money out) — posted, not paid, due within 30 days
    vendor_bills = models.execute_kw(DB, uid, PASS, 'account.move', 'search_read',
        [[['move_type', '=', 'in_invoice'],
          ['state', '=', 'posted'],
          ['payment_state', 'in', ['not_paid', 'partial']],
          ['invoice_date_due', '<=', cutoff.strftime('%Y-%m-%d')]]],
        {'fields': ['name', 'partner_id', 'amount_total', 'amount_residual',
                    'invoice_date', 'invoice_date_due', 'company_id', 'amount_residual_signed']})
    
    all_vendor = models.execute_kw(DB, uid, PASS, 'account.move', 'search_read',
        [[['move_type', '=', 'in_invoice'],
          ['state', '=', 'posted'],
          ['payment_state', 'in', ['not_paid', 'partial']]]],
        {'fields': ['name', 'partner_id', 'amount_total', 'amount_residual',
                    'invoice_date', 'invoice_date_due', 'company_id', 'amount_residual_signed']})
    
    # Build money in list
    cash_in = []
    total_in_30 = 0
    for inv in customer_invoices:
        partner = models.execute_kw(DB, uid, PASS, 'res.partner', 'read', [inv['partner_id'][0], ['name']])
        pname = partner[0].get('name', '')
        due = inv.get('amount_residual_signed') or inv.get('amount_residual') or 0
        total_in_30 += due
        cash_in.append({
            'ref': inv['name'],
            'customer': pname,
            'company': get_company_name(inv.get('company_id')),
            'due_date': (inv.get('invoice_date_due') or '')[:10],
            'amount': round(due),
            'overdue': (inv.get('invoice_date_due') or '')[:10] < today.strftime('%Y-%m-%d') if inv.get('invoice_date_due') else False
        })
    
    total_receivable = sum(
        (inv.get('amount_residual_signed') or inv.get('amount_residual') or 0)
        for inv in all_customer
    )
    
    # Build money out list
    cash_out = []
    total_out_30 = 0
    for bill in vendor_bills:
        partner = models.execute_kw(DB, uid, PASS, 'res.partner', 'read', [bill['partner_id'][0], ['name']])
        pname = partner[0].get('name', '')
        due = bill.get('amount_residual_signed') or bill.get('amount_residual') or 0
        due_abs = abs(due) if due < 0 else due
        total_out_30 += due_abs
        cash_out.append({
            'ref': bill['name'],
            'vendor': pname,
            'company': get_company_name(bill.get('company_id')),
            'due_date': (bill.get('invoice_date_due') or '')[:10],
            'amount': round(due_abs),
            'overdue': (bill.get('invoice_date_due') or '')[:10] < today.strftime('%Y-%m-%d') if bill.get('invoice_date_due') else False
        })
    
    total_payable = sum(
        abs(inv.get('amount_residual_signed') or inv.get('amount_residual') or 0)
        for inv in all_vendor
    )
    
    cash_in.sort(key=lambda x: x['due_date'])
    cash_out.sort(key=lambda x: x['due_date'])
    
    return {
        'forecast_date': today.strftime('%d-%b-%Y'),
        'forecast_until': cutoff.strftime('%d-%b-%Y'),
        'total_in_30': round(total_in_30),
        'total_out_30': round(total_out_30),
        'net_30': round(total_in_30 - total_out_30),
        'total_receivable': round(total_receivable),
        'total_payable': round(total_payable),
        'overdue_count': sum(1 for i in cash_in if i.get('overdue')),
        'cash_in': cash_in,
        'cash_out': cash_out
    }


def main():
    uid, models = connect()
    today = date.today()
    first_of_month = today.replace(day=1)
    days_elapsed = today.day

    # ── Confirmed Orders This Month ──
    order_ids = models.execute_kw(DB, uid, PASS, 'sale.order', 'search', [
        [['state', '=', 'sale'],
         ['date_order', '>=', first_of_month.strftime('%Y-%m-%d 00:00:00')],
         ['date_order', '<=', today.strftime('%Y-%m-%d 23:59:59')]]
    ])

    orders = models.execute_kw(DB, uid, PASS, 'sale.order', 'read',
        [order_ids, ['name', 'partner_id', 'amount_total', 'date_order', 'company_id']])

    # ── Order Lines ──
    daily_velocity = defaultdict(float)
    product_sales = defaultdict(lambda: {'qty': 0, 'revenue': 0, 'orders': set(), 'name': '', 'sku': ''})
    customer_sales = defaultdict(lambda: {'total': 0, 'count': 0, 'orders': [], 'name': ''})

    if order_ids:
        lines = models.execute_kw(DB, uid, PASS, 'sale.order.line', 'search_read',
            [[['order_id', 'in', order_ids]],
             ['product_id', 'product_uom_qty', 'price_subtotal', 'name']])
        for line in lines:
            pid = line['product_id'][0] if line.get('product_id') else None
            qty = line['product_uom_qty'] or 0
            subtotal = line['price_subtotal'] or 0
            pname = line['product_id'][1] if line.get('product_id') else line.get('name', 'Unknown')
            if pid:
                daily_velocity[pid] += qty
                product_sales[pid]['qty'] += qty
                product_sales[pid]['revenue'] += subtotal
                product_sales[pid]['name'] = pname

        # Get SKUs
        pids = list(product_sales.keys())
        if pids:
            prods = models.execute_kw(DB, uid, PASS, 'product.product', 'read',
                [pids, ['default_code']])
            for p in prods:
                if p['id'] in product_sales:
                    product_sales[p['id']]['sku'] = p.get('default_code', '') or ''

    # ── Process Customers ──
    for o in orders:
        pid = o['partner_id'][0] if o.get('partner_id') else None
        pname = o['partner_id'][1] if o.get('partner_id') else 'Unknown'
        amount = o['amount_total'] or 0
        if pid:
            customer_sales[pid]['name'] = pname
            customer_sales[pid]['total'] += amount
            customer_sales[pid]['count'] += 1
            customer_sales[pid]['orders'].append({
                'ref': o['name'],
                'date': (o['date_order'] or '')[:10],
                'amount': amount
            })

    # ── Stock Runout ──
    all_products = models.execute_kw(DB, uid, PASS, 'product.product', 'search_read',
        [[]], {'fields': ['id', 'name', 'default_code', 'qty_available']})

    stock_alerts = []
    critical_count = 0
    for p in all_products:
        pid = p['id']
        stock = p['qty_available'] or 0
        if stock <= 0:
            continue
        sold = daily_velocity.get(pid, 0)
        if sold == 0:
            continue
        avg_daily = sold / days_elapsed
        days_left = stock / avg_daily if avg_daily > 0 else 999
        if days_left <= 30:
            stock_alerts.append({
                'name': p['name'],
                'sku': p.get('default_code', '') or '',
                'stock': round(stock),
                'sold': round(sold),
                'daily': round(avg_daily, 2),
                'days_left': round(days_left, 1)
            })
            if days_left <= 14:
                critical_count += 1

    stock_alerts.sort(key=lambda x: x['days_left'])

    # ── Format Output ──
    month_total = sum(o['amount_total'] or 0 for o in orders)
    month_orders = len(orders)
    active_customers = len(customer_sales)

    total_revenue = sum(c['total'] for c in customer_sales.values())

    def fmt_customers():
        result = []
        for pid, data in sorted(customer_sales.items(), key=lambda x: x[1]['total'], reverse=True):
            last = max(data['orders'], key=lambda o: o['date'])['date'] if data['orders'] else ''
            result.append({
                'name': data['name'],
                'count': data['count'],
                'total': round(data['total']),
                'pct': round(data['total'] / total_revenue * 100, 1) if total_revenue else 0,
                'last_order': last
            })
        return result

    def fmt_products():
        result = []
        prod_total = sum(p['revenue'] for p in product_sales.values())
        for pid, data in sorted(product_sales.items(), key=lambda x: x[1]['revenue'], reverse=True):
            result.append({
                'name': data['name'],
                'sku': data['sku'],
                'qty': round(data['qty']),
                'revenue': round(data['revenue']),
                'order_count': 0,
                'pct': round(data['revenue'] / prod_total * 100, 1) if prod_total else 0
            })
        return result

    # ── Inventory Valuation ──
    inventory = get_inventory_valuation(uid, models)

    # ── Cash Flow Forecast ──
    cashflow = get_cashflow_forecast(uid, models)

    output = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'period': f'1-{first_of_month.strftime("%b")} to {today.strftime("%d-%b-%Y")}',
        'month_total': round(month_total),
        'month_orders': month_orders,
        'active_customers': active_customers,
        'critical_stock': critical_count,
        'products': fmt_products(),
        'customers': fmt_customers(),
        'stock_alerts': stock_alerts,
        'inventory': inventory,
        'cashflow': cashflow
    }

    with open('data.json', 'w') as f:
        json.dump(output, f, indent=2)
    print(f'✅ data.json — {month_orders} orders, {active_customers} customers, {critical_count} low-stock, Rs. {inventory["total_value"]:,} inv, Rs. {cashflow["net_30"]:,} net CF')

if __name__ == '__main__':
    main()
