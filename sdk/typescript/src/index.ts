export type Json = Record<string, unknown>;

export interface CampaignHandle {
  campaignId: string;
  clientId: string;
  clientSequence: number;
  lastEventSequence: number;
}

export interface RPGClientOptions {
  baseUrl: string;
  accessToken?: string;
}

export class RPGClient {
  readonly baseUrl: string;
  accessToken?: string;
  private campaigns = new Map<string, CampaignHandle>();

  constructor(options: RPGClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.accessToken = options.accessToken;
  }

  async bootstrap(userId: string, displayName: string, bootstrapKey: string): Promise<Json> {
    const payload = await this.request("POST", "/api/v1/auth/bootstrap", {
      user_id: userId,
      display_name: displayName,
    }, { "X-RPG-Bootstrap-Key": bootstrapKey });
    this.accessToken = String(payload.access_token);
    return payload;
  }

  async createCampaign(name: string, seed = 1, timeMode = "hybrid"): Promise<CampaignHandle> {
    const payload = await this.request("POST", "/api/v1/secure/campaigns", {
      name,
      seed,
      time_mode: timeMode,
    });
    const handle: CampaignHandle = {
      campaignId: String(payload.campaign_id),
      clientId: String(payload.owner_client_id),
      clientSequence: 1,
      lastEventSequence: 0,
    };
    this.campaigns.set(handle.campaignId, handle);
    return handle;
  }

  async joinCampaign(campaignId: string): Promise<CampaignHandle> {
    const payload = await this.request("POST", `/api/v1/secure/campaigns/${campaignId}/join`, {});
    const handle: CampaignHandle = {
      campaignId,
      clientId: String(payload.client_id),
      clientSequence: 1,
      lastEventSequence: 0,
    };
    this.campaigns.set(campaignId, handle);
    return handle;
  }

  async command(campaignId: string, command: Json, narrate = false): Promise<Json> {
    const handle = this.requireCampaign(campaignId);
    const payload = await this.request("POST", `/api/v1/reliable/campaigns/${campaignId}/commands`, {
      client_id: handle.clientId,
      client_sequence: handle.clientSequence,
      command,
      narrate,
    });
    if (!payload.duplicate) handle.clientSequence += 1;
    return payload;
  }

  reliableSocket(campaignId: string): WebSocket {
    const handle = this.requireCampaign(campaignId);
    const url = new URL(this.baseUrl.replace(/^http/, "ws") + `/api/v1/reliable/campaigns/${campaignId}/ws`);
    url.searchParams.set("client_id", handle.clientId);
    if (this.accessToken) url.searchParams.set("access_token", this.accessToken);
    return new WebSocket(url);
  }

  private requireCampaign(campaignId: string): CampaignHandle {
    const value = this.campaigns.get(campaignId);
    if (!value) throw new Error(`campaign is not joined: ${campaignId}`);
    return value;
  }

  private async request(method: string, path: string, body?: Json, extraHeaders: Record<string, string> = {}): Promise<any> {
    const headers: Record<string, string> = { "Content-Type": "application/json", ...extraHeaders };
    if (this.accessToken) headers.Authorization = `Bearer ${this.accessToken}`;
    const response = await fetch(this.baseUrl + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    return response.status === 204 ? undefined : response.json();
  }
}
