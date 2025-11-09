/**
 * API service for WanderGenie backend integration
 */

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export interface CreateTripRequest {
  prompt: string;
}

export interface TripResponse {
  trip_id: string;
  status: 'processing' | 'completed' | 'failed';
  city: string;
  origin: string;
  start_date: string;
  end_date: string;
  days: Day[];
  booking_links: BookingLinks;
  errors?: string[];
}

export interface Day {
  date: string;
  blocks: TimeBlock[];
}

export interface TimeBlock {
  start_time: string;
  end_time: string;
  poi: POI;
  travel_from_previous: number;
}

export interface POI {
  name: string;
  lat: number;
  lon: number;
  tags: string[];
  duration_min: number;
  booking_required: boolean;
  booking_url: string | null;
  notes: string | null;
  open_hours: string | null;
}

export interface BookingLinks {
  flights: string;
  hotels: string;
}

/**
 * Create a new trip (async - returns immediately with trip_id)
 */
export async function createTrip(prompt: string): Promise<{ trip_id: string; status: string }> {
  const response = await fetch(`${API_BASE_URL}/api/trip`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ prompt }),
  });

  if (!response.ok) {
    throw new Error(`Failed to create trip: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get trip details by ID (poll this to check status)
 */
export async function getTrip(tripId: string): Promise<TripResponse> {
  const response = await fetch(`${API_BASE_URL}/api/trip/${tripId}`);

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Trip not found');
    }
    throw new Error(`Failed to get trip: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Create trip synchronously (for testing - blocks until complete)
 */
export async function createTripSync(prompt: string): Promise<TripResponse> {
  const response = await fetch(`${API_BASE_URL}/api/trip/sync`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ prompt }),
  });

  if (!response.ok) {
    throw new Error(`Failed to create trip: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Edit an existing trip with natural language instruction
 */
export async function editTrip(tripId: string, instruction: string): Promise<TripResponse> {
  const response = await fetch(`${API_BASE_URL}/api/trip/${tripId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ instruction }),
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Trip not found');
    }
    if (response.status === 409) {
      throw new Error('Trip is still being generated. Please wait.');
    }
    throw new Error(`Failed to edit trip: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Poll for trip completion
 * Returns a promise that resolves when trip is complete or fails
 */
export async function pollTripUntilComplete(
  tripId: string,
  onProgress?: (status: string) => void,
  maxAttempts: number = 60,
  intervalMs: number = 2000
): Promise<TripResponse> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const trip = await getTrip(tripId);
    
    onProgress?.(trip.status);

    if (trip.status === 'completed') {
      return trip;
    }

    if (trip.status === 'failed') {
      throw new Error(trip.errors?.join(', ') || 'Trip generation failed');
    }

    // Wait before next poll
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }

  throw new Error('Trip generation timed out');
}
