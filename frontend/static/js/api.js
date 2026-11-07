/**
 * FACEGUARD AI - Centralized HTTP API Client
 * Wraps Fetch API with request timeouts, tenant auth injection, and error handling.
 */
import { Config } from './config.js';

export class ApiClient {
  constructor(timeoutMs = 12000) {
    this.timeoutMs = timeoutMs;
  }

  getHeaders(customHeaders = {}) {
    const headers = {
      'Accept': 'application/json',
      ...customHeaders,
    };
    const tenantKey = Config.getTenantKey();
    if (tenantKey) {
      headers['X-Tenant-Key'] = tenantKey;
    }
    return headers;
  }

  buildUrl(endpoint) {
    const base = Config.getApiBaseUrl().replace(/\/+$/, '');
    const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    return `${base}${path}`;
  }

  async fetchWithTimeout(url, options = {}) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });
      clearTimeout(id);
      return response;
    } catch (err) {
      clearTimeout(id);
      if (err.name === 'AbortError') {
        throw new Error(`Request timed out after ${this.timeoutMs / 1000}s`);
      }
      throw new Error(`Network failure: ${err.message || 'Unable to reach backend service'}`);
    }
  }

  async parseResponse(response) {
    const contentType = response.headers.get('content-type') || '';
    let data;

    if (contentType.includes('application/json')) {
      data = await response.json().catch(() => null);
    } else {
      data = await response.text().catch(() => null);
    }

    if (!response.ok) {
      let message = `HTTP ${response.status} ${response.statusText}`;
      if (data && typeof data === 'object') {
        message = data.detail || data.error || data.message || JSON.stringify(data);
      } else if (typeof data === 'string' && data.length > 0) {
        message = data;
      }
      const error = new Error(message);
      error.status = response.status;
      error.data = data;
      throw error;
    }

    return data;
  }

  async get(endpoint, customHeaders = {}) {
    const url = this.buildUrl(endpoint);
    const headers = this.getHeaders(customHeaders);
    const response = await this.fetchWithTimeout(url, {
      method: 'GET',
      headers,
    });
    return this.parseResponse(response);
  }

  async post(endpoint, body, customHeaders = {}) {
    const url = this.buildUrl(endpoint);
    const headers = this.getHeaders({
      'Content-Type': 'application/json',
      ...customHeaders,
    });
    const response = await this.fetchWithTimeout(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });
    return this.parseResponse(response);
  }

  async postFormData(endpoint, formData, customHeaders = {}) {
    const url = this.buildUrl(endpoint);
    // Note: Do not set Content-Type header manually for FormData, browser automatically adds boundary
    const headers = this.getHeaders(customHeaders);
    delete headers['Content-Type'];

    const response = await this.fetchWithTimeout(url, {
      method: 'POST',
      headers,
      body: formData,
    });
    return this.parseResponse(response);
  }

  /**
   * Health Check Helpers (Probes operational readiness without auth requirement)
   */
  async checkHealth() {
    const base = Config.getApiBaseUrl().replace(/\/api\/v1\/?$/, '');
    const url = `${base}/healthz`;
    const res = await this.fetchWithTimeout(url, { method: 'GET' });
    return this.parseResponse(res);
  }

  async checkReadiness() {
    const base = Config.getApiBaseUrl().replace(/\/api\/v1\/?$/, '');
    const url = `${base}/readyz`;
    const res = await this.fetchWithTimeout(url, { method: 'GET' });
    return this.parseResponse(res);
  }
}

export const api = new ApiClient();
