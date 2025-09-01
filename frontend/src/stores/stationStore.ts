import { writable, derived } from "svelte/store";
import type { Readable } from "svelte/store";
import { api, apiService } from "../services/api";
import type {
    ChargingStation,
    PaginationState,
    StationAnalysis,
    PredictionResponse,
    MonthlyContractResponse,
} from "../lib/types";

// Station data store
export const stations = writable<ChargingStation[]>([]);
export const currentStation = writable<ChargingStation | null>(null);

interface StationData {
    analysis: StationAnalysis | null;
    prediction: PredictionResponse | null;
    monthlyContract: MonthlyContractResponse | null;
}

export const stationData = writable<StationData>({
    analysis: null,
    prediction: null,
    monthlyContract: null,
});

// Loading states
export const isLoading = writable<boolean>(false);
export const isLoadingMore = writable<boolean>(false);
export const error = writable<string | null>(null);

// Upload states
export const requiresUpload = writable<boolean>(false);
export const hasData = writable<boolean>(false);
export const systemStatus = writable<any>(null);

// Pagination state
export const pagination = writable<PaginationState>({
    page: 1,
    limit: 20,
    totalPages: 1,
    hasNext: false,
    hasPrev: false,
    total: 0,
});

// Derived stores

export const stationById: Readable<Map<string, ChargingStation>> = derived(
    [stations],
    ([$stations]) => {
        const map = new Map<string, ChargingStation>();
        $stations.forEach((station) => map.set(station.id, station));
        return map;
    }
);

interface StationActions {
    loadStations: (
        reset?: boolean,
        search?: string,
        sortBy?: string,
        sortOrder?: string
    ) => Promise<void>;
    loadMore: () => Promise<void>;
    loadStationData: (stationId: string) => Promise<void>;
    setCurrentStation: (station: ChargingStation) => void;
    clearError: () => void;
    checkSystemStatus: () => Promise<void>;
    uploadCsv: (file: File) => Promise<void>;
}

// Actions
export const stationActions: StationActions = {
    async loadStations(
        reset: boolean = true,
        search?: string,
        sortBy: string = "id",
        sortOrder: string = "asc"
    ): Promise<void> {
        isLoading.set(true);
        error.set(null);

        try {
            // Use apiService.getStations to properly handle parameters including sorting
            const response = await apiService.getStations({
                limit: 9999,
                search: search,
                sortBy: sortBy,
                sortOrder: sortOrder
            });

            stations.set(response.stations || []);

            pagination.set({
                page: 1,
                limit: 9999,
                totalPages: 1,
                hasNext: false,
                hasPrev: false,
                total: (response.stations || []).length,
            });
        } catch (err: unknown) {
            const errorMessage =
                err instanceof Error ? err.message : "Unknown error occurred";

            // 500 에러는 보통 데이터가 없거나 서버 문제를 의미함
            if (
                err instanceof Error &&
                (err.message.includes("500") ||
                    err.message.includes("Internal Server Error"))
            ) {
                requiresUpload.set(true);
                hasData.set(false);
                error.set(
                    "서버에 데이터가 없습니다. CSV 파일을 업로드해주세요."
                );
            } else {
                error.set(errorMessage);

                // Check if the error indicates upload is required
                if (
                    err instanceof Error &&
                    (err.message.includes("upload") ||
                        err.message.includes("업로드"))
                ) {
                    requiresUpload.set(true);
                    hasData.set(false);
                }
            }
        } finally {
            isLoading.set(false);
            isLoadingMore.set(false);
        }
    },

    async loadMore(): Promise<void> {
        const currentPagination = await new Promise<PaginationState>(
            (resolve) => {
                const unsubscribe = pagination.subscribe((p) => {
                    resolve(p);
                    unsubscribe();
                });
            }
        );

        if (!currentPagination.hasNext) return;

        pagination.update((p) => ({ ...p, page: p.page + 1 }));
        await this.loadStations(false);
    },

    async loadStationData(stationId: string): Promise<void> {
        if (!stationId) return;

        isLoading.set(true);
        error.set(null);

        try {
            const [analysis, prediction, monthlyContract] = await Promise.all([
                apiService.getStationAnalysis(stationId),
                apiService.getPrediction(stationId),
                apiService.getMonthlyContract(
                    stationId,
                    new Date().getFullYear(),
                    new Date().getMonth() + 1
                ),
            ]);

            stationData.set({
                analysis,
                prediction,
                monthlyContract,
            });
        } catch (err: unknown) {
            const errorMessage =
                err instanceof Error ? err.message : "Unknown error occurred";
            error.set(errorMessage);
        } finally {
            isLoading.set(false);
        }
    },

    setCurrentStation(station: ChargingStation): void {
        currentStation.set(station);
    },

    clearError(): void {
        error.set(null);
    },

    async checkSystemStatus(): Promise<void> {
        try {
            const status = await apiService.getSystemStatus();
            systemStatus.set(status);
            hasData.set(status.hasData);
            requiresUpload.set(!status.hasData);
        } catch (err: unknown) {
            requiresUpload.set(true);
            hasData.set(false);
        }
    },

    async uploadCsv(file: File): Promise<void> {
        isLoading.set(true);
        error.set(null);

        try {
            const result = await apiService.uploadCsv(file);

            if (result.success) {
                requiresUpload.set(false);
                hasData.set(true);
                // Refresh station data
                await this.loadStations();
            } else {
                error.set(result.message || "업로드에 실패했습니다.");
            }
        } catch (err: unknown) {
            const errorMessage =
                err instanceof Error ? err.message : "Upload failed";
            error.set(errorMessage);
        } finally {
            isLoading.set(false);
        }
    },
};
