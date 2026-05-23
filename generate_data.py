#!/usr/bin/env python3
"""Fetch Bismillah Traders P&L data from Odoo and save as JSON for dashboard."""
import xmlrpc.client, ssl, json
ssl._create_default_https_context = ssl._create_unverified_context

URL = 'https://odoo-ss6o.srv1069133.hstgr.cloud'
DB = 'kitchen_dunya'
USER = 'msme.rs786@gmail.com'
PASS = 'sales.kitchendunya53'

common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
uid = common.authenticate(DB, USER, PASS, {})
models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')

date_from = '2025-12-01'
date_to = '2026-05-23'

income_accounts = models.execute_kw(DB, uid, PASS, 'account.account', 'search_read',
    [[['account_type', '=', 'income']]], {'fields': ['id', 'code', 'name'], 'context': {'allowed_company_ids': [3]}})
expense_accounts = models.execute_kw(DB, uid, PASS, 'account.account', 'search_read',
    [[['account_type', '=', 'expense']]], {'fields': ['id', 'code', 'name'], 'context': {'allowed_company_ids': [3]}})

income_data = []
total_income = 0
for acct in income_accounts:
    lines = models.execute_kw(DB, uid, PASS, 'account.move.line', 'search_read',
        [[['account_id', '=', acct['id']], ['date', '>=', date_from], ['date', '<=', date_to], ['parent_state', '=', 'posted']]],
        {'fields': ['debit', 'credit', 'balance', 'partner_id', 'date', 'ref', 'name'], 'context': {'allowed_company_ids': [3]}})
    bal = sum(l['balance'] for l in lines)
    if bal != 0:
        details = []
        for l in lines:
            amt = l['credit'] - l['debit']
            if abs(amt) > 0.01:
                partner = l['partner_id'][1] if isinstance(l['partner_id'], list) else ''
                details.append({'date': str(l['date']), 'partner': partner, 'amt': round(amt, 2)})
        income_data.append({'code': acct['code'], 'name': acct['name'], 'total': round(abs(bal), 2), 'details': details})
        total_income += abs(bal)

expense_data = []
total_expenses = 0
for acct in expense_accounts:
    lines = models.execute_kw(DB, uid, PASS, 'account.move.line', 'search_read',
        [[['account_id', '=', acct['id']], ['date', '>=', date_from], ['date', '<=', date_to], ['parent_state', '=', 'posted']]],
        {'fields': ['debit', 'credit', 'balance', 'partner_id', 'date', 'ref', 'name'], 'context': {'allowed_company_ids': [3]}})
    bal = sum(l['balance'] for l in lines)
    if bal != 0:
        details = []
        for l in lines:
            amt = l['debit'] - l['credit']
            if abs(amt) > 0.01:
                partner = l['partner_id'][1] if isinstance(l['partner_id'], list) else ''
                details.append({'date': str(l['date']), 'partner': partner, 'amt': round(amt, 2)})
        expense_data.append({'code': acct['code'], 'name': acct['name'], 'total': round(bal, 2), 'details': details})
        total_expenses += bal

recv_lines = models.execute_kw(DB, uid, PASS, 'account.move.line', 'search_read',
    [[['account_id', '=', 64], ['parent_state', '=', 'posted'], ['reconciled', '=', False]]],
    {'fields': ['partner_id', 'balance', 'date', 'name', 'ref'], 'context': {'allowed_company_ids': [3]}})
receivables = []
total_recv = 0
for l in recv_lines:
    bal = l['balance']
    if abs(bal) > 0.01:
        partner = l['partner_id'][1] if isinstance(l['partner_id'], list) else 'Unknown'
        receivables.append({'partner': partner, 'balance': round(bal, 2), 'date': str(l['date']), 'invoice': l['name']})
        total_recv += bal

payable_acc = models.execute_kw(DB, uid, PASS, 'account.account', 'search_read',
    [[['account_type', '=', 'liability_payable']]], {'fields': ['id', 'code', 'name'], 'context': {'allowed_company_ids': [3]}})
payables = []
total_pay = 0
for pact in payable_acc:
    pay_lines = models.execute_kw(DB, uid, PASS, 'account.move.line', 'search_read',
        [[['account_id', '=', pact['id']], ['parent_state', '=', 'posted'], ['reconciled', '=', False]]],
        {'fields': ['partner_id', 'balance', 'date', 'name', 'ref'], 'context': {'allowed_company_ids': [3]}})
    for l in pay_lines:
        bal = l['balance']
        if abs(bal) > 0.01:
            partner = l['partner_id'][1] if isinstance(l['partner_id'], list) else 'Unknown'
            payables.append({'account': pact['code'], 'partner': partner, 'balance': round(bal, 2), 'date': str(l['date']), 'ref': l['name']})
            total_pay += bal

monthly_income = {}
for acct in income_accounts:
    lines = models.execute_kw(DB, uid, PASS, 'account.move.line', 'search_read',
        [[['account_id', '=', acct['id']], ['date', '>=', '2025-12-01'], ['date', '<=', '2026-05-23'], ['parent_state', '=', 'posted']]],
        {'fields': ['balance', 'date'], 'context': {'allowed_company_ids': [3]}})
    for l in lines:
        month = str(l['date'])[:7]
        monthly_income[month] = monthly_income.get(month, 0) + abs(l['balance'])

data = {
    'company': 'Bismillah Traders',
    'period': {'from': date_from, 'to': date_to},
    'summary': {
        'total_income': round(total_income, 2),
        'total_expenses': round(total_expenses, 2),
        'net_profit': round(total_income - total_expenses, 2)
    },
    'income': income_data,
    'expenses': expense_data,
    'receivables': {'total': round(total_recv, 2), 'items': receivables},
    'payables': {'total': round(total_pay, 2), 'items': payables},
    'monthly_income': dict(sorted(monthly_income.items())),
    'generated_at': '2026-05-23'
}

with open('data.json', 'w') as f:
    json.dump(data, f, indent=2)
print("data.json updated")
