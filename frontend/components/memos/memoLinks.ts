// Builds the New Contact link for a person Jessi heard in a memo (name + company prefilled, memo attaches after Save).
export const newContactFromMemoHref = (memoId: string, person?: { name?: string; company?: string } | null) => {
  const tokens = (person?.name || '').trim().split(/\s+/).filter(Boolean);
  const q = new URLSearchParams({ memo_id: memoId });
  if (tokens[0]) q.set('first_name', tokens[0]);
  if (tokens.length > 1) q.set('last_name', tokens.slice(1).join(' '));
  if (person?.company) q.set('employer', person.company);
  return `/contact/new?${q.toString()}`;
};
