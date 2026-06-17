import { request } from "@/lib/http";
import { supabase } from "@/lib/supabase";
import { env } from "@/lib/env";

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function url(path: string): string {
  return `${env.API_BASE_URL}${path}`;
}

async function get<T>(path: string): Promise<T> {
  return request<T>(url(path), "GET", undefined, await authHeaders());
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(url(path), "POST", body, await authHeaders());
}

async function put<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(url(path), "PUT", body, await authHeaders());
}

async function patch<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(url(path), "PATCH", body, await authHeaders());
}

async function del<T>(path: string): Promise<T> {
  return request<T>(url(path), "DELETE", undefined, await authHeaders());
}

export const api = { get, post, put, patch, delete: del };
