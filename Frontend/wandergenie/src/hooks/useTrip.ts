/**
 * React hook for managing trip creation and state
 */

import { useState, useCallback } from 'react';
import { createTrip, editTrip, pollTripUntilComplete } from '../services/api';
import { convertBackendTripToFrontend, FrontendTrip } from '../utils/tripConverter';

export interface UseTripResult {
  trip: FrontendTrip | null;
  isLoading: boolean;
  error: string | null;
  progress: string | null;
  createNewTrip: (prompt: string) => Promise<void>;
  modifyTrip: (instruction: string) => Promise<void>;
  clearTrip: () => void;
}

export function useTrip(): UseTripResult {
  const [trip, setTrip] = useState<FrontendTrip | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);

  const createNewTrip = useCallback(async (prompt: string) => {
    setIsLoading(true);
    setError(null);
    setProgress('Creating trip...');

    try {
      // Step 1: Create trip (returns immediately with trip_id)
      const { trip_id } = await createTrip(prompt);
      setProgress('Generating itinerary...');

      // Step 2: Poll until complete
      const backendTrip = await pollTripUntilComplete(
        trip_id,
        (status) => {
          if (status === 'processing') {
            setProgress('Planning your perfect trip...');
          }
        }
      );

      // Step 3: Convert to frontend format
      const frontendTrip = convertBackendTripToFrontend(backendTrip);
      setTrip(frontendTrip);
      setProgress(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create trip';
      setError(errorMessage);
      setProgress(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const modifyTrip = useCallback(async (instruction: string) => {
    if (!trip) {
      setError('No trip to modify');
      return;
    }

    setIsLoading(true);
    setError(null);
    setProgress('Modifying trip...');

    try {
      // Call PATCH endpoint with edit instruction
      const backendTrip = await editTrip(trip.trip_id, instruction);
      setProgress('Updating itinerary...');

      // If backend returns processing status, poll until complete
      if (backendTrip.status === 'processing') {
        const completedTrip = await pollTripUntilComplete(
          trip.trip_id,
          (status) => {
            if (status === 'processing') {
              setProgress('Applying your changes...');
            }
          }
        );
        
        // Convert and update
        const frontendTrip = convertBackendTripToFrontend(completedTrip);
        setTrip(frontendTrip);
      } else {
        // If already complete, just convert and update
        const frontendTrip = convertBackendTripToFrontend(backendTrip);
        setTrip(frontendTrip);
      }

      setProgress(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to modify trip';
      setError(errorMessage);
      setProgress(null);
    } finally {
      setIsLoading(false);
    }
  }, [trip]);

  const clearTrip = useCallback(() => {
    setTrip(null);
    setError(null);
    setProgress(null);
  }, []);

  return {
    trip,
    isLoading,
    error,
    progress,
    createNewTrip,
    modifyTrip,
    clearTrip,
  };
}
