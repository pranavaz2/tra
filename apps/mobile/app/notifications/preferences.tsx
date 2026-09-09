import React from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Switch,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import {
  ArrowLeft,
  Bell,
  Calendar,
  Clock,
  CloudRain,
  DollarSign,
  ShieldAlert,
  Users,
  Zap,
} from 'lucide-react-native';
import { useNotificationPreferences } from '@/features/notifications/hooks/use-notification-preferences';
import { Card } from '@/shared/components/ui/Card';
import { Button } from '@/shared/components/ui/Button';

export default function NotificationPreferencesScreen() {
  const router = useRouter();
  const {
    preferences,
    isLoading,
    isSaving,
    error,
    triggerStats,
    reload,
    updateSetting,
    runIntelligenceJobNow,
  } = useNotificationPreferences();

  const handleTestJob = async () => {
    const stats = await runIntelligenceJobNow();
    if (stats) {
      Alert.alert(
        'Travel Intelligence Check Complete',
        `Evaluated: ${stats.trips_evaluated} trips\nTrip Reminders: ${stats.trip_reminders_sent}\nActivity Reminders: ${stats.activity_reminders_sent}\nWeather Alerts: ${stats.weather_alerts_sent}\nTravel Warnings: ${stats.travel_warnings_sent}`
      );
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-slate-900">
      {/* Header */}
      <View className="flex-row items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-900/90">
        <TouchableOpacity
          onPress={() => router.back()}
          className="p-2 -ml-2 rounded-full active:bg-slate-800"
        >
          <ArrowLeft size={22} color="#94a3b8" />
        </TouchableOpacity>
        <Text className="text-lg font-bold text-white">Notification Preferences</Text>
        <View className="w-8">
          {isSaving && <ActivityIndicator size="small" color="#6366f1" />}
        </View>
      </View>

      <ScrollView className="flex-1 px-4 py-4" contentContainerStyle={{ paddingBottom: 40 }}>
        {isLoading ? (
          <View className="py-20 items-center justify-center">
            <ActivityIndicator size="large" color="#6366f1" />
            <Text className="text-slate-400 mt-3 text-sm">Loading preferences...</Text>
          </View>
        ) : preferences ? (
          <>
            {/* Master Push Toggle */}
            <Card className="mb-4 bg-indigo-950/40 border border-indigo-500/30 p-4 rounded-2xl">
              <View className="flex-row items-center justify-between">
                <View className="flex-row items-center space-x-3 flex-1 mr-3">
                  <View className="w-10 h-10 rounded-xl bg-indigo-600/30 items-center justify-center">
                    <Bell size={20} color="#818cf8" />
                  </View>
                  <View className="flex-1">
                    <Text className="text-base font-bold text-white">Push Notifications</Text>
                    <Text className="text-xs text-slate-400">
                      Receive alerts on your device for trip events
                    </Text>
                  </View>
                </View>
                <Switch
                  value={preferences.push_enabled}
                  onValueChange={(val) => updateSetting({ push_enabled: val })}
                  trackColor={{ false: '#334155', true: '#4f46e5' }}
                  thumbColor={preferences.push_enabled ? '#a5b4fc' : '#94a3b8'}
                />
              </View>
            </Card>

            {/* Category Toggles */}
            <Text className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 ml-1">
              Notification Categories
            </Text>

            <Card className="mb-4 bg-slate-800/80 border border-slate-700/60 rounded-2xl divide-y divide-slate-700/50">
              {/* Trip Reminders */}
              <View className="flex-row items-center justify-between p-4">
                <View className="flex-row items-center space-x-3 flex-1 mr-3">
                  <View className="w-9 h-9 rounded-lg bg-emerald-500/20 items-center justify-center">
                    <Calendar size={18} color="#34d399" />
                  </View>
                  <View className="flex-1">
                    <Text className="text-sm font-semibold text-white">Trip Reminders</Text>
                    <Text className="text-xs text-slate-400">
                      7-day & 24-hour departure countdowns
                    </Text>
                  </View>
                </View>
                <Switch
                  value={preferences.trip_reminders}
                  disabled={!preferences.push_enabled}
                  onValueChange={(val) => updateSetting({ trip_reminders: val })}
                  trackColor={{ false: '#334155', true: '#059669' }}
                  thumbColor={preferences.trip_reminders ? '#6ee7b7' : '#94a3b8'}
                />
              </View>

              {/* Itinerary Reminders */}
              <View className="flex-row items-center justify-between p-4">
                <View className="flex-row items-center space-x-3 flex-1 mr-3">
                  <View className="w-9 h-9 rounded-lg bg-cyan-500/20 items-center justify-center">
                    <Clock size={18} color="#22d3ee" />
                  </View>
                  <View className="flex-1">
                    <Text className="text-sm font-semibold text-white">Itinerary Reminders</Text>
                    <Text className="text-xs text-slate-400">
                      2 hours before scheduled activities
                    </Text>
                  </View>
                </View>
                <Switch
                  value={preferences.itinerary_reminders}
                  disabled={!preferences.push_enabled}
                  onValueChange={(val) => updateSetting({ itinerary_reminders: val })}
                  trackColor={{ false: '#334155', true: '#0891b2' }}
                  thumbColor={preferences.itinerary_reminders ? '#67e8f9' : '#94a3b8'}
                />
              </View>

              {/* Collaboration & Invites */}
              <View className="flex-row items-center justify-between p-4">
                <View className="flex-row items-center space-x-3 flex-1 mr-3">
                  <View className="w-9 h-9 rounded-lg bg-purple-500/20 items-center justify-center">
                    <Users size={18} color="#c084fc" />
                  </View>
                  <View className="flex-1">
                    <Text className="text-sm font-semibold text-white">Collaboration</Text>
                    <Text className="text-xs text-slate-400">
                      Trip invites, member actions & role updates
                    </Text>
                  </View>
                </View>
                <Switch
                  value={preferences.collaboration}
                  disabled={!preferences.push_enabled}
                  onValueChange={(val) => updateSetting({ collaboration: val })}
                  trackColor={{ false: '#334155', true: '#7e22ce' }}
                  thumbColor={preferences.collaboration ? '#d8b4fe' : '#94a3b8'}
                />
              </View>

              {/* Budget Alerts */}
              <View className="flex-row items-center justify-between p-4">
                <View className="flex-row items-center space-x-3 flex-1 mr-3">
                  <View className="w-9 h-9 rounded-lg bg-amber-500/20 items-center justify-center">
                    <DollarSign size={18} color="#fbbf24" />
                  </View>
                  <View className="flex-1">
                    <Text className="text-sm font-semibold text-white">Budget Alerts</Text>
                    <Text className="text-xs text-slate-400">
                      Threshold warnings (75%, 90%, 100%)
                    </Text>
                  </View>
                </View>
                <Switch
                  value={preferences.budget_alerts}
                  disabled={!preferences.push_enabled}
                  onValueChange={(val) => updateSetting({ budget_alerts: val })}
                  trackColor={{ false: '#334155', true: '#d97706' }}
                  thumbColor={preferences.budget_alerts ? '#fcd34d' : '#94a3b8'}
                />
              </View>

              {/* Travel Warnings */}
              <View className="flex-row items-center justify-between p-4">
                <View className="flex-row items-center space-x-3 flex-1 mr-3">
                  <View className="w-9 h-9 rounded-lg bg-rose-500/20 items-center justify-center">
                    <ShieldAlert size={18} color="#f43f5e" />
                  </View>
                  <View className="flex-1">
                    <Text className="text-sm font-semibold text-white">Travel Warnings</Text>
                    <Text className="text-xs text-slate-400">
                      Route delays, transit risks & tight schedules
                    </Text>
                  </View>
                </View>
                <Switch
                  value={preferences.travel_warnings}
                  disabled={!preferences.push_enabled}
                  onValueChange={(val) => updateSetting({ travel_warnings: val })}
                  trackColor={{ false: '#334155', true: '#e11d48' }}
                  thumbColor={preferences.travel_warnings ? '#fda4af' : '#94a3b8'}
                />
              </View>

              {/* Weather Alerts */}
              <View className="flex-row items-center justify-between p-4">
                <View className="flex-row items-center space-x-3 flex-1 mr-3">
                  <View className="w-9 h-9 rounded-lg bg-blue-500/20 items-center justify-center">
                    <CloudRain size={18} color="#60a5fa" />
                  </View>
                  <View className="flex-1">
                    <Text className="text-sm font-semibold text-white">Weather Alerts</Text>
                    <Text className="text-xs text-slate-400">
                      Severe weather forecasts & rain advisories
                    </Text>
                  </View>
                </View>
                <Switch
                  value={preferences.weather_alerts}
                  disabled={!preferences.push_enabled}
                  onValueChange={(val) => updateSetting({ weather_alerts: val })}
                  trackColor={{ false: '#334155', true: '#2563eb' }}
                  thumbColor={preferences.weather_alerts ? '#93c5fd' : '#94a3b8'}
                />
              </View>
            </Card>

            {/* Travel Intelligence Manual Trigger Button */}
            <Card className="mb-6 bg-slate-800/40 border border-slate-700/40 p-4 rounded-2xl">
              <View className="flex-row items-center justify-between mb-3">
                <View className="flex-row items-center space-x-2">
                  <Zap size={16} color="#818cf8" />
                  <Text className="text-sm font-semibold text-white">Background Intelligence</Text>
                </View>
                <Text className="text-xs text-slate-500">Auto runs every 1h</Text>
              </View>
              <Text className="text-xs text-slate-400 mb-3">
                Simulate background scheduler execution now to check for active trip countdowns, weather, and feasibility risks.
              </Text>
              <Button
                label="Run Intelligence Check Now"
                variant="outline"
                onPress={handleTestJob}
                className="border-indigo-500/40"
              />
            </Card>
          </>
        ) : (
          <View className="py-12 items-center">
            <Text className="text-rose-400 mb-4">{error || 'Could not load settings.'}</Text>
            <Button label="Retry" onPress={reload} />
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
