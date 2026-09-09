/**
 * Collaboration API client.
 *
 * Typed operations strictly mirroring FastAPI /api/v1/trips/{trip_id}/collaboration endpoints.
 */

import { apiClient } from "@/core/api/client";
import {
  CollaborationResponse,
  MemberResponse,
  MemberListResponse,
  InvitationResponse,
  InvitationListResponse,
  ShareTokenResponse,
  InviteMemberRequest,
  ChangeMemberRoleRequest,
  PublicSharingRequest,
} from "@/core/api/types";

export class CollaborationApi {
  /**
   * Bootstrap trip collaboration for the trip.
   */
  static async createCollaboration(
    tripId: string
  ): Promise<CollaborationResponse> {
    return apiClient.post<CollaborationResponse>(
      `/api/v1/trips/${tripId}/collaboration`
    );
  }

  /**
   * Get collaboration details for a trip.
   */
  static async getCollaboration(
    tripId: string
  ): Promise<CollaborationResponse> {
    return apiClient.get<CollaborationResponse>(
      `/api/v1/trips/${tripId}/collaboration`
    );
  }

  /**
   * List members of a trip collaboration.
   */
  static async listMembers(
    tripId: string,
    limit: number = 50,
    cursor?: string
  ): Promise<MemberListResponse> {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    if (cursor) params.set("cursor", cursor);

    return apiClient.get<MemberListResponse>(
      `/api/v1/trips/${tripId}/collaboration/members?${params.toString()}`
    );
  }

  /**
   * Send an invitation to a new collaborator.
   */
  static async inviteMember(
    tripId: string,
    payload: InviteMemberRequest
  ): Promise<InvitationResponse> {
    return apiClient.post<InvitationResponse>(
      `/api/v1/trips/${tripId}/collaboration/invitations`,
      payload
    );
  }

  /**
   * List pending invitations (owner only).
   */
  static async listInvitations(
    tripId: string,
    limit: number = 50,
    cursor?: string
  ): Promise<InvitationListResponse> {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    if (cursor) params.set("cursor", cursor);

    return apiClient.get<InvitationListResponse>(
      `/api/v1/trips/${tripId}/collaboration/invitations?${params.toString()}`
    );
  }

  /**
   * Accept an invitation (invitee).
   */
  static async acceptInvitation(
    tripId: string,
    invitationId: string
  ): Promise<MemberResponse> {
    return apiClient.post<MemberResponse>(
      `/api/v1/trips/${tripId}/collaboration/invitations/${invitationId}/accept`
    );
  }

  /**
   * Decline an invitation (invitee).
   */
  static async declineInvitation(
    tripId: string,
    invitationId: string
  ): Promise<void> {
    return apiClient.post<void>(
      `/api/v1/trips/${tripId}/collaboration/invitations/${invitationId}/decline`
    );
  }

  /**
   * Revoke an invitation (owner only).
   */
  static async revokeInvitation(
    tripId: string,
    invitationId: string
  ): Promise<void> {
    return apiClient.delete<void>(
      `/api/v1/trips/${tripId}/collaboration/invitations/${invitationId}`
    );
  }

  /**
   * Change a member's role (owner only).
   */
  static async changeMemberRole(
    tripId: string,
    memberId: string,
    role: "editor" | "viewer"
  ): Promise<MemberResponse> {
    return apiClient.patch<MemberResponse>(
      `/api/v1/trips/${tripId}/collaboration/members/${memberId}`,
      { role } as ChangeMemberRoleRequest
    );
  }

  /**
   * Remove a member from the collaboration (owner only).
   */
  static async removeMember(
    tripId: string,
    memberId: string
  ): Promise<void> {
    return apiClient.delete<void>(
      `/api/v1/trips/${tripId}/collaboration/members/${memberId}`
    );
  }

  /**
   * Toggle or rotate public sharing (owner only).
   */
  static async updatePublicSharing(
    tripId: string,
    action: "enable" | "disable" | "rotate"
  ): Promise<ShareTokenResponse | null> {
    return apiClient.patch<ShareTokenResponse | null>(
      `/api/v1/trips/${tripId}/collaboration/sharing`,
      { action } as PublicSharingRequest
    );
  }

  /**
   * Get a public trip by share token (unauthenticated).
   */
  static async getPublicTrip(token: string): Promise<CollaborationResponse> {
    return apiClient.get<CollaborationResponse>(
      `/api/v1/trips/public/${token}`
    );
  }
}
