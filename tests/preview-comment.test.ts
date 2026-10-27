import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createRequire } from 'node:module';
const publish = createRequire(import.meta.url)('../cloudflare/preview-comment.cjs');

test('a successful PR preview comments with the stable branch URL and revision', async () => {
  const calls: unknown[] = [];
  const github = {rest:{issues:{listComments:()=>{}, createComment:async (args: unknown)=>calls.push(args)}}, paginate:async ()=>[]};
  await publish({github, context:{repo:{owner:'fulton-ring',repo:'nri-future-risk'}, payload:{pull_request:{number:3,head:{sha:'abcdef123456'}}}, sha:'merge-sha',runId:1}, url:'https://review-feat-fut-ad599b6f.future-risk-index-preview.pages.dev',branch:'feat/future-risk-atlas'});
  assert.equal(calls.length,1);
  const comment = calls[0] as {issue_number:number,body:string};
  assert.equal(comment.issue_number,3);
  assert.ok(comment.body.includes('https://review-feat-fut-ad599b6f.future-risk-index-preview.pages.dev'));
  assert.ok(comment.body.includes('abcdef1'));
});

test('push previews update the existing bot comment without overwriting human comments', async () => {
  const updates: {comment_id:number,body:string}[] = [];
  const marker='<!-- future-risk-cloudflare-preview -->';
  const github={rest:{pulls:{list:async ({head}:{head:string})=>{assert.equal(head,'fulton-ring:feat/future-risk-atlas');return {data:[{number:3,head:{sha:'1234567890'}}]};}}, issues:{listComments:()=>{},createComment:async ()=>assert.fail('duplicate preview comment'),updateComment:async (args:{comment_id:number,body:string})=>updates.push(args)}}, paginate:async ()=>[{id:5,user:{login:'herzo175'},body:marker},{id:7,user:{login:'github-actions[bot]'},body:marker}]};
  await publish({github,context:{repo:{owner:'fulton-ring',repo:'nri-future-risk'},payload:{},sha:'1234567890',runId:2},url:'https://def.future-risk-index-preview.pages.dev',branch:'feat/future-risk-atlas'});
  assert.equal(updates.length,1);
  assert.equal(updates[0].comment_id,7);
  assert.ok(updates[0].body.includes('https://def.future-risk-index-preview.pages.dev'));
});
