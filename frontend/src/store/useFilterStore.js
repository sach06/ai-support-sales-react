import { create } from 'zustand';

// Creates a global store with the initial values identical to streamlit session_state
export const useFilterStore = create((set) => ({
    country: 'All',
    setCountry: (country) => set({ country }),

    region: 'All',
    setRegion: (region) => set({ region }),

    equipmentType: 'All',
    setEquipmentType: (equipmentType) => set({ equipmentType }),

    companyName: 'All',
    setCompanyName: (companyName) => set({ companyName }),

    resetFilters: () => set({
        country: 'All',
        region: 'All',
        equipmentType: 'All',
        companyName: 'All'
    })
}));
