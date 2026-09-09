import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import {
  User,
  Mail,
  ShieldCheck,
  Server,
  LogOut,
  Info,
  ChevronRight,
  Bell,
} from "lucide-react-native";
import { useAuth } from "@/features/auth/context/auth-context";
import { Card } from "@/shared/components/ui/Card";
import { Button } from "@/shared/components/ui/Button";
import { ENV } from "@/core/config/env";

export default function ProfileScreen() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = () => {
    Alert.alert("Log Out", "Are you sure you want to log out of your session?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Log Out",
        style: "destructive",
        onPress: async () => {
          setIsLoggingOut(true);
          try {
            await logout();
          } finally {
            setIsLoggingOut(false);
          }
        },
      },
    ]);
  };

  return (
    <SafeAreaView className="flex-1 bg-slate-950">
      <ScrollView contentContainerStyle={{ padding: 20 }} className="flex-1">
        {/* Header */}
        <View className="mb-6">
          <Text className="text-2xl font-bold text-white tracking-tight">Account</Text>
          <Text className="text-slate-400 text-xs mt-0.5">Profile & App Settings</Text>
        </View>

        {/* User Card */}
        <Card className="p-6 bg-slate-900/90 border border-slate-800/80 mb-6 items-center">
          <View className="w-20 h-20 rounded-full bg-brand-600/20 border-2 border-brand-500/40 items-center justify-center mb-4">
            <User size={38} color="#818cf8" />
          </View>

          <Text className="text-white text-lg font-bold">
            {user?.email || "Authenticated Traveler"}
          </Text>

          <View className="flex-row items-center mt-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <ShieldCheck size={14} color="#34d399" />
            <Text className="text-emerald-400 text-xs font-semibold ml-1.5">
              Email Verified
            </Text>
          </View>
        </Card>

        {/* Account Details */}
        <Text className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-3 px-1">
          Details
        </Text>

        <Card className="p-4 bg-slate-900/60 border border-slate-800/80 mb-6 space-y-3">
          <View className="flex-row items-center justify-between py-2 border-b border-slate-800/50">
            <View className="flex-row items-center">
              <Mail size={16} color="#94a3b8" />
              <Text className="text-slate-300 text-sm ml-3">Email</Text>
            </View>
            <Text className="text-slate-400 text-sm font-medium">{user?.email}</Text>
          </View>

          <View className="flex-row items-center justify-between py-2">
            <View className="flex-row items-center">
              <Info size={16} color="#94a3b8" />
              <Text className="text-slate-300 text-sm ml-3">User ID</Text>
            </View>
            <Text className="text-slate-500 text-xs font-mono">
              {user?.user_id?.slice(0, 12)}...
            </Text>
          </View>
        </Card>

        {/* Preferences Section */}
        <Text className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-3 px-1">
          Preferences
        </Text>

        <TouchableOpacity
          onPress={() => router.push("/notifications/preferences")}
          className="mb-6 p-4 bg-slate-900/60 border border-slate-800/80 rounded-2xl flex-row items-center justify-between active:bg-slate-800/80"
        >
          <View className="flex-row items-center">
            <View className="w-9 h-9 rounded-xl bg-brand-600/20 border border-brand-500/30 items-center justify-center mr-3">
              <Bell size={18} color="#818cf8" />
            </View>
            <View>
              <Text className="text-white text-sm font-semibold">Notification Preferences</Text>
              <Text className="text-slate-400 text-xs mt-0.5">
                Trip reminders, travel warnings, quiet hours
              </Text>
            </View>
          </View>
          <ChevronRight size={18} color="#94a3b8" />
        </TouchableOpacity>

        {/* Server & App Info */}
        <Text className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-3 px-1">
          System Status
        </Text>

        <Card className="p-4 bg-slate-900/60 border border-slate-800/80 mb-8 space-y-3">
          <View className="flex-row items-center justify-between py-2 border-b border-slate-800/50">
            <View className="flex-row items-center">
              <Server size={16} color="#94a3b8" />
              <Text className="text-slate-300 text-sm ml-3">Backend Server</Text>
            </View>
            <Text className="text-brand-400 text-xs font-mono">{ENV.API_BASE_URL}</Text>
          </View>

          <View className="flex-row items-center justify-between py-2">
            <View className="flex-row items-center">
              <Info size={16} color="#94a3b8" />
              <Text className="text-slate-300 text-sm ml-3">App Version</Text>
            </View>
            <Text className="text-slate-400 text-sm">{ENV.APP_VERSION}</Text>
          </View>
        </Card>

        {/* Logout Action */}
        <Button
          label="Log Out"
          variant="danger"
          size="lg"
          icon={<LogOut size={18} color="#ffffff" />}
          onPress={handleLogout}
          isLoading={isLoggingOut}
        />
      </ScrollView>
    </SafeAreaView>
  );
}
