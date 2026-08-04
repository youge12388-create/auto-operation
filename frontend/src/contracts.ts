export function buildChannelTestPath(accountId: string): string {
  return `/api/v1/channels/accounts/${encodeURIComponent(accountId)}/test`;
}

export function buildWechatThumbPath(accountId?: string): string {
  const query = accountId ? `?account_id=${encodeURIComponent(accountId)}` : "";
  return `/api/v1/channels/wechat/materials/thumb${query}`;
}

export type WechatDraftPayload = {
  channel_account_id?: string;
  theme_id?: string;
  thumb_media_id: string;
  author?: string;
  digest?: string;
  content_source_url?: string;
};