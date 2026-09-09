import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  ArrowLeft,
  Users,
  UserPlus,
  Shield,
  Crown,
  Edit3,
  Eye,
  Mail,
  Share2,
} from "lucide-react-native";
import { useTrip } from "@/features/trips/hooks/use-trips";
import { useCollaboration } from "@/features/collaboration/hooks/use-collaboration";
import { useTripRealtime } from "@/core/realtime/use-trip-realtime";
import { TripLivePresenceBar } from "@/features/collaboration/components/TripLivePresenceBar";
import { MemberCard } from "@/features/collaboration/components/MemberCard";
import { InvitationCard } from "@/features/collaboration/components/InvitationCard";
import { InviteModal } from "@/features/collaboration/components/InviteModal";
import { RoleModal } from "@/features/collaboration/components/RoleModal";
import { PublicSharingCard } from "@/features/collaboration/components/PublicSharingCard";
import { Card } from "@/shared/components/ui/Card";
import { Button } from "@/shared/components/ui/Button";
import { ErrorMessage } from "@/shared/components/feedback/ErrorMessage";
import { LoadingScreen } from "@/shared/components/feedback/LoadingScreen";
import { MemberResponse } from "@/core/api/types";
import { useAuth } from "@/features/auth/context/auth-context";

export default function TripCollaborationScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuth();
  const { trip } = useTrip(id);

  const {
    collaboration,
    hasCollaboration,
    members,
    invitations,
    userRole,
    isOwner,
    isEditor,
    isViewer,
    isLoading,
    isMutating,
    error,
    refresh,
    createCollaboration,
    inviteMember,
    revokeInvitation,
    changeMemberRole,
    removeMember,
    togglePublicSharing,
    rotateShareToken,
  } = useCollaboration(id, trip?.owner_id);

  const { collaborators, connectionStatus } = useTripRealtime(id);

  const [refreshing, setRefreshing] = useState(false);
  const [isInviteModalVisible, setIsInviteModalVisible] = useState(false);
  const [selectedMemberForRole, setSelectedMemberForRole] =
    useState<MemberResponse | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      await refresh();
    } finally {
      setRefreshing(false);
    }
  };

  const handleBootstrap = async () => {
    setActionError(null);
    try {
      await createCollaboration();
    } catch (err: any) {
      setActionError(err.message || "Failed to enable collaboration.");
    }
  };

  const handleSendInvite = async (email: string, role: "editor" | "viewer") => {
    setActionError(null);
    await inviteMember(email, role);
    setIsInviteModalVisible(false);
  };

  const handleChangeRole = async (
    memberId: string,
    newRole: "editor" | "viewer"
  ) => {
    setActionError(null);
    await changeMemberRole(memberId, newRole);
    setSelectedMemberForRole(null);
  };

  const handleRemoveMember = async (memberId: string) => {
    setActionError(null);
    try {
      await removeMember(memberId);
    } catch (err: any) {
      setActionError(err.message || "Failed to remove member.");
    }
  };

  const handleRevokeInvitation = async (invitationId: string) => {
    setActionError(null);
    try {
      await revokeInvitation(invitationId);
    } catch (err: any) {
      setActionError(err.message || "Failed to revoke invitation.");
    }
  };

  if (isLoading && !refreshing) {
    return <LoadingScreen message="Loading collaboration..." />;
  }

  const pendingInvitations = invitations.filter((i) => i.status === "pending");

  return (
    <SafeAreaView className="flex-1 bg-slate-950" edges={["top", "bottom"]}>
      {/* Top App Bar */}
      <View className="flex-row items-center justify-between px-5 py-3 border-b border-slate-800/80 bg-slate-950">
        <TouchableOpacity
          onPress={() => router.back()}
          className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 items-center justify-center active:bg-slate-800"
          accessibilityLabel="Back to Trip"
        >
          <ArrowLeft size={18} color="#ffffff" />
        </TouchableOpacity>

        <Text className="text-white text-lg font-bold">Collaborators</Text>

        {hasCollaboration && isOwner ? (
          <TouchableOpacity
            onPress={() => {
              setActionError(null);
              setIsInviteModalVisible(true);
            }}
            className="w-10 h-10 rounded-full bg-brand-600 border border-brand-500 items-center justify-center active:bg-brand-700"
            accessibilityLabel="Invite Member"
          >
            <UserPlus size={18} color="#ffffff" />
          </TouchableOpacity>
        ) : (
          <View className="w-10" />
        )}
      </View>

      {/* Live Presence Bar */}
      <TripLivePresenceBar
        collaborators={collaborators}
        connectionStatus={connectionStatus}
      />

      <ScrollView
        className="flex-1"
        contentContainerStyle={{ padding: 20 }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#6366f1"
            colors={["#6366f1"]}
          />
        }
      >
        {/* Error Banners */}
        {error && <ErrorMessage message={error} className="mb-4" />}
        {actionError && <ErrorMessage message={actionError} className="mb-4" />}

        {!hasCollaboration ? (
          /* Not Bootstrapped State */
          <Card className="p-8 bg-slate-900/80 border border-slate-800 items-center text-center mt-6">
            <View className="w-16 h-16 rounded-2xl bg-brand-500/10 border border-brand-500/20 items-center justify-center mb-4">
              <Users size={32} color="#818cf8" />
            </View>
            <Text className="text-white text-xl font-bold mb-2">
              Trip Collaboration
            </Text>
            <Text className="text-slate-400 text-sm text-center mb-6 leading-5">
              Plan together with friends and co-travelers. Enable collaboration to
              invite editors, assign read-only viewers, or generate a public view link.
            </Text>
            <Button
              label="Enable Collaboration"
              onPress={handleBootstrap}
              isLoading={isMutating}
              className="w-full"
            />
          </Card>
        ) : (
          /* Active Collaboration Experience */
          <>
            {/* User Access Overview Card */}
            <Card className="p-5 bg-slate-900 border border-slate-800 mb-6">
              <View className="flex-row items-center justify-between mb-3">
                <View className="flex-row items-center">
                  <View className="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 items-center justify-center mr-3">
                    {isOwner ? (
                      <Crown size={20} color="#818cf8" />
                    ) : isEditor ? (
                      <Edit3 size={20} color="#38bdf8" />
                    ) : (
                      <Eye size={20} color="#34d399" />
                    )}
                  </View>
                  <View>
                    <Text className="text-slate-400 text-xs font-semibold uppercase">
                      Your Access
                    </Text>
                    <Text className="text-white text-base font-bold capitalize">
                      {userRole ? `${userRole} Access` : "Collaborator"}
                    </Text>
                  </View>
                </View>

                <View className="px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700">
                  <Text className="text-slate-300 text-xs font-semibold">
                    {members.length} {members.length === 1 ? "Member" : "Members"}
                  </Text>
                </View>
              </View>

              <Text className="text-slate-400 text-xs leading-4">
                {isOwner
                  ? "You own this trip. You can invite collaborators, assign Editor/Viewer roles, and manage public link sharing."
                  : isEditor
                  ? "You are an Editor. You can add and edit itinerary days, items, and log expenses."
                  : "You are a Viewer. You have read-only access to this trip and its itinerary."}
              </Text>
            </Card>

            {/* Public Sharing (Owner only) */}
            {isOwner && collaboration && (
              <PublicSharingCard
                isPublic={collaboration.is_public}
                shareToken={collaboration.share_token}
                onToggle={togglePublicSharing}
                onRotate={async () => {
                  await rotateShareToken();
                }}
                isMutating={isMutating}
              />
            )}

            {/* Members Section */}
            <View className="flex-row items-center justify-between mb-3">
              <View className="flex-row items-center">
                <Users size={16} color="#94a3b8" />
                <Text className="text-slate-300 text-xs font-semibold uppercase tracking-wider ml-2">
                  Members ({members.length})
                </Text>
              </View>

              {isOwner && (
                <TouchableOpacity
                  onPress={() => {
                    setActionError(null);
                    setIsInviteModalVisible(true);
                  }}
                  className="flex-row items-center px-2.5 py-1 rounded-lg bg-brand-600/20 border border-brand-500/30 active:bg-brand-600/30"
                >
                  <UserPlus size={13} color="#818cf8" />
                  <Text className="text-brand-300 text-xs font-semibold ml-1">
                    Invite
                  </Text>
                </TouchableOpacity>
              )}
            </View>

            <View className="mb-6">
              {members.map((member) => (
                <MemberCard
                  key={member.member_id}
                  member={member}
                  isCurrentUser={member.user_id === user?.user_id}
                  canManage={isOwner}
                  onChangeRole={(m) => setSelectedMemberForRole(m)}
                  onRemove={handleRemoveMember}
                  isMutating={isMutating}
                />
              ))}
            </View>

            {/* Pending Invitations Section (Owner only) */}
            {isOwner && (
              <View className="mb-6">
                <View className="flex-row items-center justify-between mb-3">
                  <View className="flex-row items-center">
                    <Mail size={16} color="#94a3b8" />
                    <Text className="text-slate-300 text-xs font-semibold uppercase tracking-wider ml-2">
                      Pending Invitations ({pendingInvitations.length})
                    </Text>
                  </View>
                </View>

                {pendingInvitations.length === 0 ? (
                  <Card className="p-5 bg-slate-900/60 border border-dashed border-slate-800 items-center justify-center">
                    <Text className="text-slate-400 text-xs">
                      No pending invitations. Tap "Invite" to add collaborators.
                    </Text>
                  </Card>
                ) : (
                  <View>
                    {pendingInvitations.map((inv) => (
                      <InvitationCard
                        key={inv.invitation_id}
                        invitation={inv}
                        onRevoke={handleRevokeInvitation}
                        isMutating={isMutating}
                      />
                    ))}
                  </View>
                )}
              </View>
            )}
          </>
        )}
      </ScrollView>

      {/* Modals */}
      <InviteModal
        visible={isInviteModalVisible}
        onClose={() => setIsInviteModalVisible(false)}
        onSubmit={handleSendInvite}
        isSubmitting={isMutating}
      />

      <RoleModal
        visible={!!selectedMemberForRole}
        onClose={() => setSelectedMemberForRole(null)}
        member={selectedMemberForRole}
        onSubmit={handleChangeRole}
        isSubmitting={isMutating}
      />
    </SafeAreaView>
  );
}
