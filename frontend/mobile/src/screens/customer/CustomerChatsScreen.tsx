import { getCustomerChatRooms } from "../../api/chat";
import { ChatRoomList } from "../../components/ChatRoomList";
import { ScreenContainer } from "../../components/ScreenContainer";

export function CustomerChatsScreen() {
  return (
    <ScreenContainer>
      <ChatRoomList loadRooms={getCustomerChatRooms} viewerRole="customer" />
    </ScreenContainer>
  );
}
