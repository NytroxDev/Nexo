from veltix import MessageType

FILE_META  = MessageType(201, "file_meta")
FILE_CHUNK = MessageType(202, "file_chunk")
FILE_DONE  = MessageType(203, "file_done")
FILE_ACK   = MessageType(204, "file_ack")
FILE_ERR   = MessageType(205, "file_err")
