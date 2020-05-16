from odoo import models, fields, api, _

class contractAcc(models.TransientModel):
    _name = 'dms.contract.acc.wiz'

    wage = fields.Integer('Wage', required=True)

    @api.multi
    def writeWage(self):
        active_id = self._context.get('active_id')
        contract_id = self.env['hr.contract'].browse(active_id)

        print('active ID : ', active_id)
        print('contract ID : ', contract_id)
        for contract in contract_id:
            if contract:
                contract.write({'wage' : self.wage})
                contract.state = 'hrmang'

        return {'type': 'ir.actions.act_window_close'}