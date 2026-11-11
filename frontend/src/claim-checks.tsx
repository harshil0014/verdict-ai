
type CheckedClaim = {
  field?: string;
  value?: string;
  source_check?: string;
  structured_check?: string;
  semantic_support?: string;
};

const readable = (value: string) => value.replaceAll('_', ' ');

export function ClaimChecks({claim}: {claim: CheckedClaim}) {
  const missing = 'Not recorded in this revision';
  const field = claim.field?.trim();
  const value = claim.value?.trim();
  const literalLabels: Record<string, string> = {
    value_in_quote: 'Extracted value text found in quote',
    value_not_found_in_quote: 'Extracted value text not found in quote',
    not_comparable: 'No extracted value to compare',
  };
  return <>
    <dl>
      <dt>Source existence</dt>
      <dd>{readable(claim.source_check || 'not assessed in prior revision')}</dd>
      <dt>Extracted field</dt>
      <dd>{field ? readable(field) : missing}</dd>
      <dt>Extracted value</dt>
      <dd>{value ? <code>{claim.value}</code> : missing}</dd>
      <dt>Literal value check</dt>
      <dd>{literalLabels[claim.structured_check || ''] || readable(claim.structured_check || 'not assessed in prior revision')}</dd>
      <dt>Semantic support</dt>
      <dd>{readable(claim.semantic_support || 'not assessed')} · AI assessed</dd>
    </dl>
    {claim.structured_check === 'value_not_found_in_quote' && <p>
      This checks the extracted value shown above, not every number in the claim.
      A missing literal match does not invalidate the source quote. Semantic support is assessed separately.
    </p>}
    {claim.structured_check && (!field || !value) && <p>
      This saved revision does not record the field or value behind the literal check.
    </p>}
  </>;
}
