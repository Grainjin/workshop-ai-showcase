import { getProviderChatRooms } from "../../api/chat";
import { ChatRoomList } from "../../components/ChatRoomList";
import { ScreenContainer } from "../../components/ScreenContainer";

export function ProviderChatsScreen() {
  return (
    <ScreenContainer>
      <ChatRoomList loadRooms={getProviderChatRooms} viewerRole="provider" />
    </ScreenContainer>
  );
}
