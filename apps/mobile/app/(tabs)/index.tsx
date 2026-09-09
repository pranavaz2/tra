import React, { useState, useRef } from "react";
import {
  View,
  Text,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  TextInput,
  Keyboard,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import {
  Sparkles,
  Calendar,
  ChevronRight,
  MapPin,
  ArrowRight,
} from "lucide-react-native";
import { useAuth } from "@/features/auth/context/auth-context";
import { useTrips } from "@/features/trips/hooks/use-trips";
import { Card } from "@/shared/components/ui/Card";
import { StatusBadge } from "@/shared/components/ui/StatusBadge";
import { Button } from "@/shared/components/ui/Button";

/** Lightweight NL parser â€” no external dependencies. */
function parseNLInput(text: string): Record<string, string | undefined> {
  const result: Record<string, string | undefined> = {};

  const durMatch = text.match(/(\d+)\s*(?:-\s*)?days?/i);
  if (durMatch) result.durationDays = durMatch[1];

  const budgetMatch = text.match(/[â‚¹$â‚¬Â£]?\s*([\d,]+k?)\s*(?:rupees?|inr|usd|budget)?/i);
  if (budgetMatch) {
    let raw = budgetMatch[1].replace(/,/g, "");
    if (raw.toLowerCase().endsWith("k")) raw = String(parseInt(raw) * 1000);
    result.targetBudget = raw;
  }
  result.currency =
    text.includes("â‚¹") || /rupees?|inr/i.test(text) ? "INR" : "USD";

  if (/relaxed?|slow|chill|easy|leisure/i.test(text)) result.travelStyle = "relaxed";
  else if (/active|packed|intense|adventure/i.test(text)) result.travelStyle = "active";
  else result.travelStyle = "balanced";

  const interestMap: Array<[RegExp, string]> = [
    [/history|heritage|palace|fort|temple|monument/i, "History & Museums"],
    [/food|cuisine|dining|eat|restaurant|street food/i, "Food & Dining"],
    [/nature|outdoors|trek|hike|mountain|forest|wildlife/i, "Outdoors & Nature"],
    [/beach|sea|coast|surf/i, "Beaches"],
    [/art|museum|gallery|culture/i, "Art & Architecture"],
    [/market|shop|bazaar/i, "Local Markets"],
    [/family|kids|child/i, "Family Friendly"],
  ];
  const interests = interestMap.filter(([re]) => re.test(text)).map(([, l]) => l);
  if (interests.length) result.interests = interests.join(",");

  const destMatch = text.match(
    /(?:days?\s+in|trip\s+to|visit|explore|going\s+to|in)\s+([A-Za-z\s]+?)(?:,|\s+for|\s+with|\s+[â‚¹$]|\s+\d|\.|$)/i
  );
  if (destMatch) {
    const dest = destMatch[1].trim();
    if (dest.length >= 2 && dest.length <= 100) result.destination = dest;
  }

  return result;
}

const DEFAULT_CHIPS = [
  { label: "ðŸ° Mysore Heritage & Food", dest: "Mysore, India" },
  { label: "ðŸ–ï¸ Goa Beach Getaway", dest: "Goa, India" },
  { label: "â›°ï¸ Coorg Nature Trail", dest: "Coorg, India" },
];

export default function HomeScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const { trips, isLoading, isRefreshing, refresh } = useTrips();

  const [nlInput, setNlInput] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef<TextInput>(null);

  const userDisplayName = user?.email ? user.email.split("@")[0] : "Traveler";

  const dynamicChips = React.useMemo(() => {
    const seen = new Set<string>();
    const chips: { label: string; dest: string }[] = [];
    const emojis = ["ðŸ“", "ðŸ—ºï¸", "âœˆï¸"];
    for (const t of trips) {
      const dest = t.title?.split(",")[0]?.trim();
      if (dest && !seen.has(dest) && chips.length < 3) {
        seen.add(dest);
        chips.push({ label: `${emojis[chips.length]} ${dest}`, dest: t.title });
      }
    }
    return chips.length > 0 ? chips : DEFAULT_CHIPS;
  }, [trips]);

  const handleNLSubmit = () => {
    Keyboard.dismiss();
    const text = nlInput.trim();
    const parsed = parseNLInput(text);
    router.push({
      pathname: "/trips/new",
      params: { nlInput: text || undefined, ...parsed },
    } as any);
  };

  return (
    <SafeAreaView className="flex-1 bg-slate-950">
      <ScrollView
        contentContainerStyle={{ paddingBottom: 40 }}
        refreshControl={
          <RefreshControl refreshing={isRefreshing} onRefresh={refresh} tintColor="#6366f1" />
        }
        className="px-5 pt-3"
        keyboardShouldPersistTaps="handled"
      >
        {/* Greeting */}
        <View className="mb-5">
          <Text className="text-slate-400 text-xs font-semibold uppercase tracking-wider">
            Welcome back
          </Text>
          <Text className="text-2xl font-bold text-white tracking-tight">
            Hello, {userDisplayName} ðŸ‘‹
          </Text>
        </View>

        {/* Hero AI Input Card */}
        <Card className="bg-gradient-to-br from-brand-900/80 via-slate-900 to-slate-950 border-brand-500/40 p-5 mb-6 overflow-hidden shadow-xl shadow-brand-950/50">
          <View className="flex-row items-center justify-between mb-3">
            <View className="px-3 py-1 rounded-full bg-brand-500/20 border border-brand-400/40 flex-row items-center">
              <Sparkles size={13} color="#38bdf8" />
              <Text className="text-brand-300 text-xs font-bold ml-1.5">Travix AI</Text>
            </View>
            <View className="px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20">
              <Text className="text-emerald-400 text-[10px] font-semibold">Real Verified Places</Text>
            </View>
          </View>

          <Text className="text-white text-xl font-extrabold mb-1 tracking-tight">
            Where do you want to go?
          </Text>
          <Text className="text-slate-400 text-xs mb-4 leading-relaxed">
            Just tell Travix â€” destination, days, budget, anything.
          </Text>

          <View
            className={`flex-row items-center rounded-2xl border ${
              isFocused ? "bg-slate-800 border-brand-500" : "bg-slate-900/90 border-slate-700"
            } px-4 py-3 mb-4`}
          >
            <TextInput
              ref={inputRef}
              value={nlInput}
              onChangeText={setNlInput}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              onSubmitEditing={handleNLSubmit}
              placeholder={`"3 days in Mysore, â‚¹12,000, history & food"`}
              placeholderTextColor="#475569"
              className="flex-1 text-white text-sm"
              multiline
              maxLength={300}
              returnKeyType="go"
              blurOnSubmit
            />
            <TouchableOpacity
              onPress={handleNLSubmit}
              className={`ml-3 w-9 h-9 rounded-xl items-center justify-center ${
                nlInput.trim() ? "bg-brand-600 active:bg-brand-500" : "bg-slate-800"
              }`}
              accessibilityLabel="Plan my trip"
            >
              <ArrowRight size={17} color={nlInput.trim() ? "#ffffff" : "#475569"} />
            </TouchableOpacity>
          </View>

          <View className="flex-row flex-wrap">
            {dynamicChips.map((chip) => (
              <TouchableOpacity
                key={chip.dest}
                onPress={() =>
                  router.push({ pathname: "/trips/new", params: { destination: chip.dest } } as any)
                }
                className="px-2.5 py-1.5 rounded-xl bg-slate-900/90 border border-brand-500/30 active:bg-brand-600/20 mr-1.5 mb-1.5"
              >
                <Text className="text-slate-200 text-xs font-medium">{chip.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </Card>

        {/* Quick Stats */}
        <View className="flex-row space-x-3 mb-8">
          <Card className="flex-1 p-4 bg-slate-900/80 mr-2">
            <Text className="text-slate-400 text-xs font-medium">Total Trips</Text>
            <Text className="text-white text-2xl font-bold mt-1">
              {isLoading ? "..." : trips.length}
            </Text>
          </Card>
          <Card className="flex-1 p-4 bg-slate-900/80 ml-2">
            <Text className="text-slate-400 text-xs font-medium">Active / Planned</Text>
            <Text className="text-emerald-400 text-2xl font-bold mt-1">
              {isLoading
                ? "..."
                : trips.filter((t) => t.status === "active" || t.status === "planned").length}
            </Text>
          </Card>
        </View>

        {/* Recent Trips */}
        <View className="flex-row items-center justify-between mb-4">
          <Text className="text-lg font-bold text-white">Recent Trips</Text>
          <TouchableOpacity onPress={() => router.push("/(tabs)/trips")}>
            <Text className="text-brand-400 text-sm font-semibold">View All</Text>
          </TouchableOpacity>
        </View>

        {isLoading && !isRefreshing ? (
          <View className="py-8 items-center">
            <Text className="text-slate-500 text-sm">Loading your trips...</Text>
          </View>
        ) : trips.length === 0 ? (
          <Card className="p-8 items-center justify-center bg-slate-900/40 border-dashed border-slate-800">
            <View className="w-12 h-12 rounded-full bg-slate-800 items-center justify-center mb-3">
              <MapPin size={24} color="#64748b" />
            </View>
            <Text className="text-white font-semibold text-base mb-1">No trips yet</Text>
            <Text className="text-slate-400 text-xs text-center mb-4">
              Type your destination above â€” Travix will plan everything
            </Text>
            <Button
              label="Plan Your First Trip"
              variant="outline"
              size="sm"
              onPress={() => router.push("/trips/new")}
            />
          </Card>
        ) : (
          <View className="space-y-3">
            {trips.slice(0, 4).map((trip) => (
              <TouchableOpacity
                key={trip.trip_id}
                activeOpacity={0.7}
                onPress={() =>
                  router.push({ pathname: "/trips/[id]", params: { id: trip.trip_id } })
                }
                className="mb-3"
              >
                <Card className="p-4 bg-slate-900/80 flex-row items-center justify-between">
                  <View className="flex-1 mr-3">
                    <View className="flex-row items-center mb-1.5">
                      <StatusBadge status={trip.status} />
                      <Text className="text-slate-400 text-xs ml-2.5 font-medium capitalize">
                        {trip.privacy.replace("_", " ")}
                      </Text>
                    </View>
                    <Text className="text-white font-bold text-base" numberOfLines={1}>
                      {trip.title}
                    </Text>
                    <View className="flex-row items-center mt-2">
                      <Calendar size={13} color="#94a3b8" />
                      <Text className="text-slate-400 text-xs ml-1.5">
                        {trip.departure_date
                          ? `${trip.departure_date}${trip.return_date ? ` â†’ ${trip.return_date}` : ""}`
                          : trip.is_date_flexible
                          ? "Flexible dates"
                          : "Dates not set"}
                      </Text>
                    </View>
                  </View>
                  <ChevronRight size={20} color="#64748b" />
                </Card>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
