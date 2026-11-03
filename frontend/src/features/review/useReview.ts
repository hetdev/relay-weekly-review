// Data hook with stale-response protection: every parameter change aborts the
// in-flight request AND a sequence guard drops any late response, so a slow
// old request can never overwrite a newer filter selection.

import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  fetchAccounts,
  fetchReviewOptions,
  fetchWeeklyReview,
  type Account,
  type ReviewOptions,
  type ReviewResponse,
} from "./api";
import type { Metric, ReviewQuery } from "./api";
import type { UrlFilters } from "./urlState";

interface ReviewState {
  accounts: Account[];
  accountsError: string | null;
  options: ReviewOptions | null;
  review: ReviewResponse | null;
  loading: boolean;
  error: { message: string; code: string } | null;
}

export function useReview(filters: UrlFilters): ReviewState & { reload: () => void } {
  const [state, setState] = useState<ReviewState>({
    accounts: [],
    accountsError: null,
    options: null,
    review: null,
    loading: true,
    error: null,
  });
  const [reloadCounter, setReloadCounter] = useState(0);
  const sequence = useRef(0);

  useEffect(() => {
    const currentSequence = ++sequence.current;
    const controller = new AbortController();
    const isCurrent = () => sequence.current === currentSequence;
    const apply = (patch: Partial<ReviewState>) => {
      if (isCurrent()) setState((previous) => ({ ...previous, ...patch }));
    };

    let cancelled = false;
    const onAbort = () => {
      cancelled = true;
    };
    controller.signal.addEventListener("abort", onAbort);

    (async () => {
      setState((previous) => ({ ...previous, loading: true, error: null }));
      try {
        const accounts = await fetchAccounts(controller.signal);
        if (cancelled || !isCurrent()) return;
        if (accounts.length === 0) {
          apply({ accounts, loading: false, review: null, options: null });
          return;
        }
        const account =
          filters.account && accounts.some((candidate) => candidate.id === filters.account)
            ? filters.account
            : accounts[0].id;
        const options = await fetchReviewOptions(account, controller.signal);
        if (cancelled || !isCurrent()) return;

        const week =
          filters.week && options.available_weeks.includes(filters.week)
            ? filters.week
            : options.default_week;
        const location =
          filters.location && options.locations.includes(filters.location)
            ? filters.location
            : "";

        const query: ReviewQuery = {
          accountId: account,
          weekStart: week,
          metric: filters.metric as Metric,
          location: location || null,
        };
        const review = await fetchWeeklyReview(query, controller.signal);
        if (cancelled || !isCurrent()) return;
        apply({ accounts, options, review, loading: false, error: null });
      } catch (error) {
        if (cancelled || !isCurrent() || controller.signal.aborted) return;
        if (error instanceof ApiError) {
          apply({ loading: false, error: { message: error.message, code: error.code } });
        } else {
          apply({
            loading: false,
            error: { message: "Could not reach the review service.", code: "network" },
          });
        }
      }
    })();

    return () => {
      controller.signal.removeEventListener("abort", onAbort);
      controller.abort();
    };
  }, [filters.account, filters.week, filters.metric, filters.location, reloadCounter]);

  return { ...state, reload: () => setReloadCounter((counter) => counter + 1) };
}
