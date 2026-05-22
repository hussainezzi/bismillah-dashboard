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

    output = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'period': f'1-{first_of_month.strftime("%b")} to {today.strftime("%d-%b-%Y")}',
        'month_total': round(month_total),
        'month_orders': month_orders,
        'active_customers': active_customers,
        'critical_stock': critical_count,
        'products': fmt_products(),
        'customers': fmt_customers(),
        'stock_alerts': stock_alerts
    }

    with open('data.json', 'w') as f:
        json.dump(output, f, indent=2)
    print(f'✅ data.json generated — {month_orders} orders, {active_customers} customers, {critical_count} low-stock items')

if __name__ == '__main__':
    main()
