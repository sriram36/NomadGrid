import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { api, fieldErrors, NetworkError } from '../api/client';
import { toView } from '../api/adapt';
import { toApiRequest } from '../lib/request';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [meta, setMeta] = useState(null);
  const [currentPackage, setCurrentPackageRaw] = useState(null);
  const [lastRequest, setLastRequest] = useState(null);     // the last request sent, in the form's own shape
  const [outcome, setOutcome] = useState(null);              // OVER_BUDGET / NO_PACKAGE details for the outcome page
  const [variants, setVariants] = useState(null);            // the three-package comparison
  const [isGenerating, setIsGenerating] = useState(false);
  const [undoAvailable, setUndoAvailable] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);
  const [swapModalState, setSwapModalState] = useState({ isOpen: false, modalType: null, targetItem: null, targetDate: null });

  // Dropdown values and rules come from the backend, never from the UI.
  useEffect(() => {
    api.meta().then(({ status, data }) => { if (status === 200) setMeta(data); }).catch(() => {});
  }, []);

  const showToast = useCallback((text, type = 'success') => {
    setToastMessage({ text, type });
    setTimeout(() => setToastMessage(null), 4500);
  }, []);

  const setPackage = useCallback((pkg) => setCurrentPackageRaw(pkg ? toView(pkg) : null), []);

  const failure = useCallback((e) => {
    const message = e instanceof NetworkError ? e.message : 'Something went wrong. Please try again.';
    showToast(message, 'error');
    return { kind: 'ERROR', message };
  }, [showToast]);

  // ---- M1/M2/M8/G4: build a package (or the three-package comparison). Returns what happened; the caller navigates.
  const submitTrip = useCallback(async (request, mode = 'single') => {
    setIsGenerating(true);
    setOutcome(null);
    setVariants(null);
    setLastRequest(request);
    try {
      const body = toApiRequest(request);
      const { status, data } = mode === 'compare' ? await api.variants(body) : await api.build(body);
      if (status === 422) return { kind: 'INVALID', fields: fieldErrors(data), message: data?.error?.message };
      if (status !== 200 || !data) return { kind: 'ERROR', message: data?.error?.message || 'The server could not build a package.' };
      if (data.outcome === 'PACKAGE') {
        setPackage(data.package);
        setUndoAvailable(false);
        return { kind: 'PACKAGE', id: data.package.package_id };
      }
      if (data.outcome === 'VARIANTS') {
        setVariants(data);
        return { kind: 'VARIANTS' };
      }
      setOutcome({ ...data, kind: data.outcome, request });
      return { kind: data.outcome };
    } catch (e) {
      return failure(e);
    } finally {
      setIsGenerating(false);
    }
  }, [setPackage, failure]);

  // ---- open a saved package by id (works after a page refresh and a backend restart)
  const loadPackage = useCallback(async (id) => {
    try {
      const { status, data } = await api.getPackage(id);
      if (status !== 200) return null;
      setPackage(data);
      setUndoAvailable(false);
      return data;
    } catch (e) {
      failure(e);
      return null;
    }
  }, [setPackage, failure]);

  // ---- M7: confirm
  const handleConfirmBooking = useCallback(async () => {
    if (!currentPackage) return { ok: false };
    try {
      const { status, data } = await api.confirm(currentPackage.package_id);
      if (status === 200) {
        setPackage(data.package);
        setUndoAvailable(false);
        showToast(`Reservation #${data.reservation_number} confirmed!`);
        return { ok: true, number: data.reservation_number };
      }
      const message = data?.error?.message || 'We could not confirm this booking.';
      showToast(message, 'error');
      return { ok: false, conflict: data?.error?.code === 'INVENTORY_CONFLICT', message };
    } catch (e) {
      return { ok: false, ...failure(e) };
    }
  }, [currentPackage, setPackage, showToast, failure]);

  // ---- M7: look a reservation up by its 10-digit number. Returns the package or null ("not found").
  const handleLookupReservation = useCallback(async (number) => {
    try {
      const { status, data } = await api.reservation(number);
      if (status === 200) {
        setPackage(data);
        setUndoAvailable(false);
        return data;
      }
      return null;
    } catch (e) {
      failure(e);
      return null;
    }
  }, [setPackage, failure]);

  // ---- M6/G3: apply one change. The backend re-checks the whole package and answers APPLIED / REFUSED /
  // BUDGET_EXCEEDED / PINNED_CONFLICT. APPLIED updates the screen; the others are returned for the dialog to explain.
  const applyChange = useCallback(async (op) => {
    if (!currentPackage) return null;
    try {
      const { data } = await api.change(currentPackage.package_id, op);
      if (data?.result === 'APPLIED') {
        setPackage(data.package);
        setUndoAvailable(Boolean(data.undo_available));
        const extra = (data.knock_on || []).join(' ');
        showToast(`${data.summary}${extra ? ' ' + extra : ''}`);
      }
      return data;
    } catch (e) {
      failure(e);
      return null;
    }
  }, [currentPackage, setPackage, showToast, failure]);

  const handleRemoveAttraction = useCallback(async (item) => {
    const res = await applyChange({ op: 'REMOVE_ATTRACTION', item_id: item.item_id });
    if (res && res.result !== 'APPLIED') showToast(res.reason || res.message || 'That change could not be made.', 'error');
  }, [applyChange, showToast]);

  const handleUndo = useCallback(async () => {
    if (!currentPackage) return;
    try {
      const { data } = await api.undo(currentPackage.package_id);
      if (data?.result === 'UNDONE') {
        setPackage(data.package);
        setUndoAvailable(Boolean(data.undo_available));
        showToast(data.summary);
      } else {
        setUndoAvailable(false);
        showToast(data?.reason || 'There is nothing to undo.', 'error');
      }
    } catch (e) {
      failure(e);
    }
  }, [currentPackage, setPackage, showToast, failure]);

  const handleResetTrip = useCallback(() => {
    setCurrentPackageRaw(null);
    setOutcome(null);
    setVariants(null);
    setUndoAvailable(false);
  }, []);

  return (
    <AppContext.Provider value={{
      meta, currentPackage, lastRequest, outcome, variants, isGenerating, undoAvailable, toastMessage,
      swapModalState, setSwapModalState,
      showToast, submitTrip, loadPackage, handleConfirmBooking, handleLookupReservation,
      applyChange, handleRemoveAttraction, handleUndo, handleResetTrip,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
