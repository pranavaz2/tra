/**
 * TypeScript API models strictly mirroring Travix FastAPI backend schemas.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Common & Envelopes
// ─────────────────────────────────────────────────────────────────────────────

export interface DataEnvelope<T> {
  data: T;
}

export interface ValidationErrorParam {
  name: string;
  reason: string;
}

export interface ApiProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
  error_code?: string;
  trace_id?: string;
  invalid_params?: ValidationErrorParam[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Authentication Types
// ─────────────────────────────────────────────────────────────────────────────

export interface DeviceInfoRequest {
  device_name?: string | null;
  platform?: "ios" | "android" | "web" | null;
  app_version?: string | null;
  os_version?: string | null;
}

export interface SessionResponse {
  session_id: string;
  device_name: string | null;
  created_at: string;
}

export interface UserResponse {
  user_id: string;
  email: string;
  is_email_verified: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
  device_info?: DeviceInfoRequest | null;
  locale?: string | null;
  timezone?: string | null;
}

export interface RegisterRequest {
  email: string;
  password: string;
  device_info?: DeviceInfoRequest | null;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface LogoutRequest {
  refresh_token?: string | null;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  access_token_expires_at: string;
  refresh_token_expires_at: string;
  session: SessionResponse;
  user: UserResponse;
}

export interface RegisterResponse {
  user_id: string;
  email: string;
  requires_verification: boolean;
  message?: string | null;
  access_token?: string | null;
  refresh_token?: string | null;
  token_type?: string | null;
  access_token_expires_at?: string | null;
  refresh_token_expires_at?: string | null;
  session?: SessionResponse | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Trips Types
// ─────────────────────────────────────────────────────────────────────────────

export type TripStatus = "draft" | "planned" | "active" | "completed" | "archived";
export type TripPrivacy = "private" | "link_only" | "public";

export interface TripResponse {
  trip_id: string;
  owner_id: string;
  title: string;
  status: TripStatus;
  privacy: TripPrivacy;
  departure_date: string | null;
  return_date: string | null;
  is_date_flexible: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface TripPageResponse {
  items: TripResponse[];
  next_cursor: string | null;
}

export interface TripCreateRequest {
  title: string;
  privacy?: TripPrivacy | null;
  departure_date?: string | null;
  return_date?: string | null;
  is_date_flexible?: boolean;
}

export interface TripUpdateRequest {
  title?: string | null;
  privacy?: TripPrivacy | null;
  new_status?: TripStatus | null;
  update_dates?: boolean;
  departure_date?: string | null;
  return_date?: string | null;
  is_date_flexible?: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// Itinerary Types
// ─────────────────────────────────────────────────────────────────────────────

export type ItineraryItemType = "activity" | "transport" | "lodging" | "restaurant";

export interface ItineraryItemResponse {
  item_id: string;
  day_id: string;
  title: string;
  item_type: ItineraryItemType;
  description: string | null;
  start_time: string | null;
  end_time: string | null;
  location_id: string | null;
  cost: number | null;
  currency: string | null;
  created_at: string;
  updated_at: string;
}

export interface ItineraryDayResponse {
  day_id: string;
  day_number: number;
  title: string | null;
  date: string | null;
  items: ItineraryItemResponse[];
  created_at: string;
  updated_at: string;
}

export interface ItineraryResponse {
  itinerary_id: string;
  trip_id: string;
  days: ItineraryDayResponse[];
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ItineraryDayCreateRequest {
  day_number: number;
  title?: string | null;
  date?: string | null;
}

export interface ItineraryDayUpdateRequest {
  day_number: number;
  title?: string | null;
  date?: string | null;
}

export interface ItineraryItemCreateRequest {
  day_id: string;
  title: string;
  item_type: ItineraryItemType;
  description?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  location_id?: string | null;
  cost?: number | null;
  currency?: string | null;
}

export interface ItineraryItemUpdateRequest {
  day_id?: string | null;
  title: string;
  item_type: ItineraryItemType;
  description?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  location_id?: string | null;
  cost?: number | null;
  currency?: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Travel Planning & Proposal Types
// ─────────────────────────────────────────────────────────────────────────────

export type ProposalStatus =
  | "queued"
  | "generating"
  | "ready"
  | "accepted"
  | "rejected"
  | "failed"
  | "expired";

export type BudgetLevel = "budget" | "mid_range" | "luxury";
export type TravelStyle = "relaxed" | "balanced" | "active";

export interface ProposalPreferences {
  destination: string;
  duration_days: number;
  budget_level: BudgetLevel;
  interests: string[];
  travel_style: TravelStyle;
  special_requirements: string;
}

export interface ProposedActivityResponse {
  title: string;
  description: string;
  category: string;
  duration_minutes: number;
  estimated_cost: string | null;
  provider_place_id: string | null;
  place_name: string | null;
  formatted_address: string | null;
  latitude: number | null;
  longitude: number | null;
  rating: number | null;
  is_verified: boolean;
}

export interface ProposedDayResponse {
  day_number: number;
  title: string;
  description: string;
  activities: ProposedActivityResponse[];
}

export interface PlanningResultResponse {
  summary: string;
  days: ProposedDayResponse[];
  estimated_total_cost: string | null;
  generated_at: string;
}

export interface ProposalResponse {
  proposal_id: string;
  trip_id: string;
  owner_id: string;
  preferences: ProposalPreferences;
  status: ProposalStatus;
  result: PlanningResultResponse | null;
  failure_reason: string | null;
  expires_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface ProposalCreateRequest {
  destination: string;
  duration_days: number;
  budget_level: BudgetLevel;
  interests?: string[];
  travel_style: TravelStyle;
  special_requirements?: string;
  /** Preferred cost currency code. Default: "INR". */
  currency?: string;
  /** Optional total trip budget as a numeric string (e.g. "15000"). */
  target_budget?: string;
}

export interface ProposalPageResponse {
  items: ProposalResponse[];
  next_cursor: string | null;
  has_more: boolean;
  limit: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Budget & Expense Types
// ─────────────────────────────────────────────────────────────────────────────

export type BudgetStatus = "active" | "closed";
export type ExpenseType = "activity" | "transport" | "lodging" | "restaurant" | "other";

export interface CategoryResponse {
  category_id: string;
  name: string;
  description: string | null;
  icon: string | null;
}

export interface BudgetResponse {
  budget_id: string;
  trip_id: string;
  owner_id: string;
  limit: number;
  limit_amount?: number;
  currency: string;
  status: BudgetStatus;
  total_spent: number;
  remaining: number;
  spent_percentage: number;
  categories: CategoryResponse[];
  created_at: string;
  updated_at: string;
}

export interface BudgetSummaryResponse {
  budget: BudgetResponse;
  category_breakdowns: Record<string, number>;
  type_breakdowns: Record<string, number>;
}

export interface BudgetCreateRequest {
  limit_amount: number;
  currency: string;
}

export interface BudgetUpdateRequest {
  limit_amount?: number | null;
  status?: BudgetStatus | null;
}

export interface ExpenseResponse {
  expense_id: string;
  title: string;
  amount: number;
  currency: string;
  category_id: string;
  expense_type: ExpenseType;
  description: string | null;
  expense_date: string;
  created_at: string;
}

export interface ExpenseListResponse {
  items: ExpenseResponse[];
  next_cursor: string | null;
  has_more: boolean;
  limit: number;
}

export interface ExpenseCreateRequest {
  title: string;
  amount: number;
  category_id: string;
  expense_type: ExpenseType;
  expense_date: string; // YYYY-MM-DD
  description?: string | null;
}

export interface ExpenseUpdateRequest {
  title?: string | null;
  amount?: number | null;
  category_id?: string | null;
  expense_type?: ExpenseType | null;
  expense_date?: string | null;
  description?: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Collaboration & Sharing Types
// ─────────────────────────────────────────────────────────────────────────────

export type MemberRole = "owner" | "editor" | "viewer";
export type InvitationStatus =
  | "pending"
  | "accepted"
  | "declined"
  | "expired"
  | "revoked";

export interface MemberResponse {
  member_id: string;
  user_id: string;
  role: MemberRole;
  joined_at: string;
}

export interface MemberListResponse {
  items: MemberResponse[];
  next_cursor: string | null;
  has_more: boolean;
  limit: number;
}

export interface InvitationResponse {
  invitation_id: string;
  invitee_email: string;
  role: MemberRole;
  status: InvitationStatus;
  expires_at: string;
  created_at: string;
}

export interface InvitationListResponse {
  items: InvitationResponse[];
  next_cursor: string | null;
  has_more: boolean;
  limit: number;
}

export interface CollaborationResponse {
  collaboration_id: string;
  trip_id: string;
  owner_id: string;
  member_count: number;
  is_public: boolean;
  share_token: string | null;
  created_at: string;
  updated_at: string;
}

export interface ShareTokenResponse {
  share_token: string;
  is_public: boolean;
}

export interface InviteMemberRequest {
  invitee_email: string;
  role: "editor" | "viewer";
}

export interface ChangeMemberRoleRequest {
  role: "editor" | "viewer";
}

export interface PublicSharingRequest {
  action: "enable" | "disable" | "rotate";
}

// ─────────────────────────────────────────────────────────────────────────────
// Media & Attachments Types
// ─────────────────────────────────────────────────────────────────────────────

export type MediaType = "photo" | "video" | "note" | "voice_memo" | "receipt";
export type MediaStatus = "available" | "processing" | "deleted";

export interface MediaItemResponse {
  media_id: string;
  collection_id: string;
  url: string;
  media_type: MediaType;
  status: MediaStatus;
  mime_type: string;
  size_bytes: number;
  file_name: string | null;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  caption: string | null;
  uploaded_by: string;
  activity_id: string | null;
  expense_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface MediaListResponse {
  items: MediaItemResponse[];
  next_cursor: string | null;
  has_more: boolean;
  limit: number;
}

export interface MediaCaptionUpdateRequest {
  caption: string | null;
}

export interface AttachActivityRequest {
  activity_id: string;
}

export interface AttachExpenseRequest {
  expense_id: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// AI Assistant Types
// ─────────────────────────────────────────────────────────────────────────────

export type AssistantResponseType = "informational" | "recommendation" | "proposed_mutation";
export type AssistantActionType =
  | "read_trip"
  | "read_itinerary"
  | "read_budget"
  | "read_expenses"
  | "read_media"
  | "search_places"
  | "get_place_details"
  | "find_nearby_places"
  | "check_itinerary_conflicts"
  | "check_travel_feasibility"
  | "check_budget_risks"
  | "check_weather_forecast"
  | "estimate_travel_time"
  | "check_route_between_activities"
  | "propose_itinerary_change"
  | "propose_adding_activity"
  | "propose_adding_place"
  | "propose_removing_activity"
  | "propose_rescheduling_activity"
  | "propose_replacing_activity"
  | "propose_reordering_activities"
  | "propose_adjusting_budget"
  | "propose_adding_expense"
  | "propose_updating_budget_limit";

export type ActionStatus = "pending" | "applied" | "rejected" | "expired";

export type WarningCategory = "timing" | "distance" | "budget" | "feasibility" | "weather";
export type WarningSeverity = "info" | "warning" | "critical";

export interface TravelWarningMetadata {
  estimated_duration_minutes?: number;
  route_distance_km?: number;
  travel_mode?: string;
  is_fallback?: boolean;
  is_verified_coordinates?: boolean;
  gap_minutes?: number;
  estimated_distance_km?: number;
  [key: string]: any;
}

export interface TravelWarning {
  warning_id: string;
  category: WarningCategory;
  severity: WarningSeverity;
  title: string;
  message: string;
  day_number?: number | null;
  item_ids: string[];
  metadata: TravelWarningMetadata;
}


export interface TripWarningsResponse {
  trip_id: string;
  warnings: TravelWarning[];
  total_warnings: number;
  has_critical: boolean;
  itinerary_conflicts_count: number;
  budget_risks_count: number;
}

export interface ChatMessageSchema {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: string | null;
}

export interface PersistedMessageSchema {
  message_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  response_type?: AssistantResponseType | null;
  action_id?: string | null;
  tools_used: AssistantActionType[];
  created_at: string;
}

export interface ConversationHistoryResponse {
  conversation_id: string;
  trip_id: string;
  user_id: string;
  messages: PersistedMessageSchema[];
}

export interface ProposedActionSchema {
  action_id: string;
  trip_id: string;
  action_type: AssistantActionType;
  summary: string;
  description: string;
  payload: Record<string, any>;
  status: ActionStatus;
  created_at: string;
  applied_at?: string | null;
}

export interface ChatAssistantRequest {
  message: string;
  history?: ChatMessageSchema[];
}

export interface ChatAssistantResponse {
  message: string;
  response_type: AssistantResponseType;
  proposed_action?: ProposedActionSchema | null;
  tools_used: AssistantActionType[];
}

export interface ConfirmActionResponse {
  action: ProposedActionSchema;
  itinerary?: ItineraryResponse | null;
  expense?: ExpenseResponse | null;
  budget?: BudgetResponse | null;
  message: string;
}

export interface RejectActionResponse {
  action: ProposedActionSchema;
  message: string;
}

