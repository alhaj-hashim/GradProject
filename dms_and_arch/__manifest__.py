{
    'name': 'DMS & Archive',
    'version': '1.0',
    'summary': 'manage all the processes on files',
    'description': """
Documents Management System
===========================

This application enables you to manage all the processes on files and manage a tracking file process 
after a file is done you can save it on the archive side
""",
    'category': 'Master',
    'sequence': 1,
    'author': 'Group of Project',
    'website': 'www.example.com',
    'depends': ['base', 'muk_dms', 'hr', 'hr_contract', 'hr_holidays', 'hr_payroll'],
    'data': [
        'security/dms_and_arch_security.xml',
        'security/ir.model.access.csv',
        'report/dms_view_report.xml',
        'report/dms_leave_template.xml',
        'report/dms_hr_contract_template.xml',
        'wizard/reject_lev_view.xml',
        'views/dms_view.xml',
        'wizard/contract_accounting_view.xml',
        'views/dms_contract_view.xml',
        'data/dms_data.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False
}