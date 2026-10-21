/** Current public PRD narrative for material labels; never recorded-result proof. */
export const NARRATIVE_BASIS = Object.freeze({
  path: 'PRD.md', section: '15',
  gitBlob: '264d37353099b51c13fd683e771fc35fbf829939',
  sha256: 'b3989a91f1d3f7a1de6812fa05777d0dfdf84a4eee4a7909bdda77d1196032ce',
  requirementLabelsOnly: true, scenarioSemanticsVerified: false,
});
export const DEMO_NARRATIVE = Object.freeze([
  {id:'DEMO-01',title:'Single bill-of-lading transfer',mainSource:'REG_DIRECT',
    requiredOutcome:'Transfer A to B, register B and release original AB funds; retain bill history without physical collection or collection-driven burn.'},
  {id:'DEMO-02',title:'Continuous trading and prefix release',mainSource:'REG_ELECTRONIC',
    requiredOutcome:'Trade A to B to C to D; release each eligible original segment independently as holder advances.'},
  {id:'DEMO-03',title:'Registration of B is refused',mainSource:'REG_INTERMEDIARY',
    requiredOutcome:'Return owner D directly to effective holder A, unwind the unregistered suffix and refund original buyers; account for gas separately.'},
  {id:'DEMO-04',title:'Refused registration of C preserves AB',mainSource:'REG_DIRECT',
    requiredOutcome:'Preserve registered and settled AB; return owner D directly to effective holder B and unwind only BC/CD.'},
  {id:'DEMO-05',title:'Intermediate ordinary-wallet ETH shortage',mainSource:'REG_ELECTRONIC',
    requiredOutcome:'Prearranged authorized return remains possible when intermediate ordinary wallets lack ETH; no temporary custody or forced sale.'},
  {id:'DEMO-06',title:'Cutoff failure and recovery boundary',mainSource:'REG_INTERMEDIARY',
    requiredOutcome:'Reject a new trade at cutoff, recover the overdue unregistered suffix to effective holder and preserve the completed prefix; no expired reopening or collection-driven burn.'},
].map(value=>Object.freeze(value)));
