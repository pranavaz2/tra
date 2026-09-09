import React, { useState } from "react";
import {
  Modal,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  Image,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from "react-native";
import {
  X,
  Upload,
  Image as ImageIcon,
  Camera,
  FileCheck,
  AlertCircle,
  Tag,
} from "lucide-react-native";
import * as ImagePicker from "expo-image-picker";
import { Button } from "@/shared/components/ui/Button";
import { FileUploadPayload } from "../api/media-api";

interface MediaUploadModalProps {
  visible: boolean;
  onClose: () => void;
  onUpload: (file: FileUploadPayload, caption?: string) => Promise<any>;
  isUploading?: boolean;
}

export const MediaUploadModal: React.FC<MediaUploadModalProps> = ({
  visible,
  onClose,
  onUpload,
  isUploading = false,
}) => {
  const [selectedFile, setSelectedFile] = useState<FileUploadPayload | null>(null);
  const [previewUri, setPreviewUri] = useState<string | null>(null);
  const [caption, setCaption] = useState("");
  const [error, setError] = useState<string | null>(null);

  const resetState = () => {
    setSelectedFile(null);
    setPreviewUri(null);
    setCaption("");
    setError(null);
  };

  const handleClose = () => {
    resetState();
    onClose();
  };

  const handlePickImage = async () => {
    setError(null);
    try {
      const permissionResult =
        await ImagePicker.requestMediaLibraryPermissionsAsync();

      if (!permissionResult.granted) {
        Alert.alert(
          "Permission Required",
          "Permission to access your photo library is required to upload pictures."
        );
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        allowsEditing: false,
        quality: 0.85,
      });

      if (!result.canceled && result.assets && result.assets.length > 0) {
        const asset = result.assets[0];
        const uri = asset.uri;
        const uriParts = uri.split("/");
        const rawName = asset.fileName || uriParts[uriParts.length - 1] || "photo.jpg";
        const mimeType = asset.mimeType || "image/jpeg";

        setSelectedFile({
          uri,
          name: rawName,
          type: mimeType,
        });
        setPreviewUri(uri);
      }
    } catch (err: any) {
      setError("Failed to open image picker: " + (err?.message || "Unknown error"));
    }
  };

  const handleTakePhoto = async () => {
    setError(null);
    try {
      const permissionResult =
        await ImagePicker.requestCameraPermissionsAsync();

      if (!permissionResult.granted) {
        Alert.alert(
          "Permission Required",
          "Permission to access the camera is required to take photos."
        );
        return;
      }

      const result = await ImagePicker.launchCameraAsync({
        allowsEditing: false,
        quality: 0.85,
      });

      if (!result.canceled && result.assets && result.assets.length > 0) {
        const asset = result.assets[0];
        const uri = asset.uri;
        const uriParts = uri.split("/");
        const rawName = asset.fileName || uriParts[uriParts.length - 1] || "camera_photo.jpg";
        const mimeType = asset.mimeType || "image/jpeg";

        setSelectedFile({
          uri,
          name: rawName,
          type: mimeType,
        });
        setPreviewUri(uri);
      }
    } catch (err: any) {
      setError("Failed to open camera: " + (err?.message || "Unknown error"));
    }
  };

  const handleSubmit = async () => {
    if (!selectedFile) {
      setError("Please select a file or take a photo first.");
      return;
    }

    setError(null);
    try {
      await onUpload(selectedFile, caption.trim() || undefined);
      handleClose();
    } catch (err: any) {
      setError(err?.message || "Upload failed. Please try again.");
    }
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={true}
      onRequestClose={handleClose}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        className="flex-1 justify-end bg-black/60"
      >
        <View className="bg-slate-900 border-t border-slate-800 rounded-t-3xl p-6">
          {/* Header */}
          <View className="flex-row items-center justify-between pb-4 border-b border-slate-800 mb-4">
            <View className="flex-row items-center">
              <View className="w-8 h-8 rounded-lg bg-brand-600/20 border border-brand-500/30 items-center justify-center mr-2.5">
                <Upload size={16} color="#818cf8" />
              </View>
              <Text className="text-white text-lg font-bold">Add Trip Media</Text>
            </View>
            <TouchableOpacity
              onPress={handleClose}
              className="w-8 h-8 rounded-full bg-slate-800 items-center justify-center"
            >
              <X size={18} color="#94a3b8" />
            </TouchableOpacity>
          </View>

          {/* Error Banner */}
          {error && (
            <View className="p-3 bg-rose-950/50 border border-rose-800/50 rounded-xl mb-4 flex-row items-center">
              <AlertCircle size={16} color="#f43f5e" />
              <Text className="text-rose-400 text-xs font-medium ml-2 flex-1">
                {error}
              </Text>
            </View>
          )}

          {/* Selection Area / Preview */}
          {!previewUri ? (
            <View className="flex-row gap-3 mb-5">
              <TouchableOpacity
                onPress={handlePickImage}
                disabled={isUploading}
                className="flex-1 p-5 rounded-2xl bg-slate-950 border border-slate-800 items-center justify-center active:bg-slate-800"
              >
                <View className="w-12 h-12 rounded-xl bg-sky-500/10 border border-sky-500/20 items-center justify-center mb-2">
                  <ImageIcon size={22} color="#38bdf8" />
                </View>
                <Text className="text-white text-xs font-bold mb-0.5">
                  Photo Library
                </Text>
                <Text className="text-slate-500 text-[10px]">
                  Select from gallery
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                onPress={handleTakePhoto}
                disabled={isUploading}
                className="flex-1 p-5 rounded-2xl bg-slate-950 border border-slate-800 items-center justify-center active:bg-slate-800"
              >
                <View className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 items-center justify-center mb-2">
                  <Camera size={22} color="#34d399" />
                </View>
                <Text className="text-white text-xs font-bold mb-0.5">
                  Take Photo
                </Text>
                <Text className="text-slate-500 text-[10px]">
                  Use device camera
                </Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View className="mb-5 bg-slate-950 border border-slate-800 rounded-2xl p-3 flex-row items-center justify-between">
              <View className="flex-row items-center flex-1 mr-3">
                <Image
                  source={{ uri: previewUri }}
                  className="w-14 h-14 rounded-xl mr-3 bg-slate-900"
                  resizeMode="cover"
                />
                <View className="flex-1">
                  <View className="flex-row items-center">
                    <FileCheck size={13} color="#10b981" />
                    <Text className="text-emerald-400 text-xs font-semibold ml-1.5" numberOfLines={1}>
                      File Selected
                    </Text>
                  </View>
                  <Text className="text-slate-400 text-[11px] mt-0.5" numberOfLines={1}>
                    {selectedFile?.name}
                  </Text>
                </View>
              </View>

              <TouchableOpacity
                onPress={resetState}
                disabled={isUploading}
                className="px-2.5 py-1.5 rounded-lg bg-slate-800 border border-slate-700"
              >
                <Text className="text-slate-300 text-xs font-medium">Change</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Caption Input */}
          <View className="mb-6">
            <Text className="text-slate-300 text-xs font-semibold uppercase mb-1.5">
              Caption / Notes (Optional)
            </Text>
            <View className="flex-row items-center bg-slate-800 border border-slate-700 rounded-xl px-3 py-1">
              <Tag size={16} color="#94a3b8" />
              <TextInput
                value={caption}
                onChangeText={setCaption}
                placeholder="e.g. Dinner in Shibuya or Boarding Pass"
                placeholderTextColor="#64748b"
                maxLength={500}
                editable={!isUploading}
                className="flex-1 ml-2 py-3 text-white text-sm"
              />
            </View>
          </View>

          {/* Submit Button */}
          <Button
            label="Upload Media"
            onPress={handleSubmit}
            isLoading={isUploading}
            disabled={!selectedFile}
            className="w-full"
          />
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
};
