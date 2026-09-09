/**
 * useCollaboration Hook.
 *
 * Manages trip collaboration, members, pending invitations, public sharing,
 * and role-derived authorization state.
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { CollaborationApi } from "../api/collaboration-api";
import { useAuth } from "@/features/auth/context/auth-context";
import {
  CollaborationResponse,
  MemberResponse,
  InvitationResponse,
  MemberRole,
  InviteMemberRequest,
} from "@/core/api/types";
import { TravixApiError } from "@/core/api/client";

export function useCollaboration(tripId?: string, tripOwnerId?: string) {
  const { user } = useAuth();
  const [collaboration, setCollaboration] =
    useState<CollaborationResponse | null>(null);
  const [members, setMembers] = useState<MemberResponse[]>([]);
  const [invitations, setInvitations] = useState<InvitationResponse[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isMutating, setIsMutating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Compute current user's role
  const userRole = useMemo<MemberRole | null>(() => {
    if (!user) return null;
    const currentUserId = user.user_id;

    if (tripOwnerId && currentUserId === tripOwnerId) return "owner";
    if (collaboration && currentUserId === collaboration.owner_id) return "owner";

    const memberEntry = members.find((m) => m.user_id === currentUserId);
    if (memberEntry) return memberEntry.role;

    return null;
  }, [user, tripOwnerId, collaboration, members]);

  const isOwner = userRole === "owner";
  const isEditor = userRole === "editor";
  const isViewer = userRole === "viewer";
  const canEdit = isOwner || isEditor;

  const fetchCollaborationData = useCallback(async () => {
    if (!tripId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      let collabData: CollaborationResponse | null = null;
      try {
        collabData = await CollaborationApi.getCollaboration(tripId);
        setCollaboration(collabData);
      } catch (err: any) {
        if (err instanceof TravixApiError && err.status === 404) {
          // Collaboration not bootstrapped yet
          setCollaboration(null);
          setMembers([]);
          setInvitations([]);
          return;
        }
        throw err;
      }

      if (collabData) {
        // Fetch members
        try {
          const membersData = await CollaborationApi.listMembers(tripId, 100);
          setMembers(membersData.items || []);
        } catch (memberErr) {
          console.warn("Failed to load members", memberErr);
        }

        // Fetch invitations if requester is the owner
        const currentUserId = user?.user_id;
        const isCurrentOwner =
          (tripOwnerId && currentUserId === tripOwnerId) ||
          currentUserId === collabData.owner_id;

        if (isCurrentOwner) {
          try {
            const invData = await CollaborationApi.listInvitations(tripId, 50);
            setInvitations(invData.items || []);
          } catch (invErr) {
            console.warn("Failed to load invitations", invErr);
          }
        } else {
          setInvitations([]);
        }
      }
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to load collaboration details.";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [tripId, tripOwnerId, user?.user_id]);

  useEffect(() => {
    fetchCollaborationData();
  }, [fetchCollaborationData]);

  // Bootstrap collaboration
  const createCollaboration = async (): Promise<CollaborationResponse> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);
    try {
      const created = await CollaborationApi.createCollaboration(tripId);
      await fetchCollaborationData();
      return created;
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to initialize collaboration.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  // Invite member
  const inviteMember = async (
    email: string,
    role: "editor" | "viewer"
  ): Promise<InvitationResponse> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);
    try {
      const payload: InviteMemberRequest = {
        invitee_email: email.trim().toLowerCase(),
        role,
      };
      const inv = await CollaborationApi.inviteMember(tripId, payload);
      await fetchCollaborationData();
      return inv;
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to send invitation.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  // Revoke invitation
  const revokeInvitation = async (invitationId: string): Promise<void> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);
    try {
      await CollaborationApi.revokeInvitation(tripId, invitationId);
      await fetchCollaborationData();
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to revoke invitation.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  // Accept invitation
  const acceptInvitation = async (invitationId: string): Promise<MemberResponse> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);
    try {
      const member = await CollaborationApi.acceptInvitation(tripId, invitationId);
      await fetchCollaborationData();
      return member;
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to accept invitation.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  // Decline invitation
  const declineInvitation = async (invitationId: string): Promise<void> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);
    try {
      await CollaborationApi.declineInvitation(tripId, invitationId);
      await fetchCollaborationData();
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to decline invitation.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  // Change member role
  const changeMemberRole = async (
    memberId: string,
    role: "editor" | "viewer"
  ): Promise<MemberResponse> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);
    try {
      const updated = await CollaborationApi.changeMemberRole(
        tripId,
        memberId,
        role
      );
      await fetchCollaborationData();
      return updated;
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to update member role.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  // Remove member
  const removeMember = async (memberId: string): Promise<void> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);
    try {
      await CollaborationApi.removeMember(tripId, memberId);
      await fetchCollaborationData();
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to remove member.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  // Toggle public sharing
  const togglePublicSharing = async (enable: boolean): Promise<void> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);
    try {
      await CollaborationApi.updatePublicSharing(
        tripId,
        enable ? "enable" : "disable"
      );
      await fetchCollaborationData();
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to update public sharing.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  // Rotate share token
  const rotateShareToken = async (): Promise<string | null> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);
    try {
      const res = await CollaborationApi.updatePublicSharing(tripId, "rotate");
      await fetchCollaborationData();
      return res?.share_token || null;
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to rotate share link.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  return {
    collaboration,
    hasCollaboration: !!collaboration,
    members,
    invitations,
    userRole,
    isOwner,
    isEditor,
    isViewer,
    canEdit,
    isLoading,
    isMutating,
    error,
    refresh: fetchCollaborationData,
    createCollaboration,
    inviteMember,
    revokeInvitation,
    acceptInvitation,
    declineInvitation,
    changeMemberRole,
    removeMember,
    togglePublicSharing,
    rotateShareToken,
  };
}
