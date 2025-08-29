import type {
    StationsResponse,
    StationAnalysis,
    PredictionResponse,
    MonthlyContractResponse,
    ApiError,
} from "../lib/types.ts";
import type { RequestInit } from "node-fetch"; // 브라우저 환경이면 제거해도 됨

const BASE = ""; // dev: Vite 프록시 사용, prod: 같은 오리진

async function handle(res: Response) {
    if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(
            `${res.status} ${res.statusText}${text ? ` - ${text}` : ""}`
        );
    }
    const ct = res.headers.get("content-type") || "";
    return ct.includes("application/json") ? res.json() : res.text();
}

export const api = {
    get: (path: string, init?: RequestInit) =>
        fetch(`${BASE}/api${path}`, { method: "GET", ...init }).then(handle),
    post: (path: string, body?: BodyInit, init?: RequestInit) =>
        fetch(`${BASE}/api${path}`, { method: "POST", body, ...init }).then(
            handle
        ),
    del: (path: string, init?: RequestInit) =>
        fetch(`${BASE}/api${path}`, { method: "DELETE", ...init }).then(handle),
};

export const apiService = {
    getSystemStatus: () => api.get("/status"),
    getStations: (params?: {
        page?: number;
        limit?: number;
        search?: string;
        sortBy?: string;
        sortOrder?: string;
    }) => {
        const q = new URLSearchParams();
        if (params?.page) q.set("page", String(params.page));
        if (params?.limit) q.set("limit", String(params.limit));
        if (params?.search) q.set("search", params.search);
        if (params?.sortBy) q.set("sort_by", params.sortBy);
        if (params?.sortOrder) q.set("sort_order", params.sortOrder);
        const qs = q.toString();
        return api.get(`/stations${qs ? `?${qs}` : ""}`);
    },
    getStationAnalysis: (stationId: string) =>
        api.get(`/station-analysis/${encodeURIComponent(stationId)}`),
    getPrediction: (stationId: string) =>
        api.get(`/stations/${encodeURIComponent(stationId)}/prediction`),
    getEnergyDemandForecast: (stationId: string, days: number = 90) =>
        api.get(`/stations/${encodeURIComponent(stationId)}/energy-demand-forecast?days=${days}`),
    getMonthlyContract: (
        stationId: string,
        year: number,
        month: number,
        mode: "p95" | "max" = "p95",
        roundKw = 1
    ) =>
        api.get(
            `/stations/${encodeURIComponent(
                stationId
            )}/monthly-contract?year=${year}&month=${month}&mode=${mode}&round_kw=${roundKw}`
        ),
    uploadCsv: (file: File) => {
        const form = new FormData();
        form.append("file", file);
        form.append("file_type", "charging_sessions");
        return api.post("/admin/upload-csv", form);
    },
};
