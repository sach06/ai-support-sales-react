import { create } from 'zustand';

// Creates a global store with the initial values identical to streamlit session_state
export const useDataStore = create((set) => ({
    dataLoaded: false,
    setDataLoaded: (dataLoaded) => set({ dataLoaded }),

    availableFiles: [],
    setAvailableFiles: (availableFiles) => set({ availableFiles }),

    logs: [],
    addLog: (log) => set((state) => ({ logs: [...state.logs, log] })),
    clearLogs: () => set({ logs: [] }),

    databaseStatus: null,
    setDatabaseStatus: (databaseStatus) => set({ databaseStatus }),
}));
