// Keep one deployment comment per PR, including previews triggered by branch pushes.
module.exports = async ({github, context, url, branch}) => {
  const preview = new URL(url);
  if (preview.protocol !== 'https:' || !preview.hostname.endsWith('.future-risk-index-preview.pages.dev')) {
    throw new Error('Unexpected Cloudflare preview URL');
  }
  const {owner, repo} = context.repo;
  const pulls = context.payload.pull_request
    ? [context.payload.pull_request]
    : (await github.rest.pulls.list({owner, repo, state:'open', head:`${owner}:${branch}`})).data;
  const marker = '<!-- future-risk-cloudflare-preview -->';
  for (const pull of pulls) {
    const revision = pull.head?.sha || context.sha;
    const body = `${marker}\n**Cloudflare preview**\n\n[Open preview](${preview.href}) · [Build](https://github.com/${owner}/${repo}/actions/runs/${context.runId})\n\nCommit: \`${revision.slice(0,7)}\``;
    const comments = await github.paginate(github.rest.issues.listComments, {owner, repo, issue_number:pull.number, per_page:100});
    const prior = comments.find(comment => comment.user?.login === 'github-actions[bot]' && comment.body?.includes(marker));
    if (prior) await github.rest.issues.updateComment({owner, repo, comment_id:prior.id, body});
    else await github.rest.issues.createComment({owner, repo, issue_number:pull.number, body});
  }
  return {commentedPullRequests:pulls.map(pull=>pull.number)};
};
